package vrp

import (
	"context"
	"github.com/interuss/dss/pkg/api/v1/vrppb"

	"github.com/interuss/dss/pkg/auth"
	dsserr "github.com/interuss/dss/pkg/errors"
	dssmodels "github.com/interuss/dss/pkg/models"
	scdmodels "github.com/interuss/dss/pkg/scd/models"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/interuss/dss/pkg/vrp/repos"
	"github.com/interuss/stacktrace"
	"github.com/jonboulle/clockwork"
)

var (
	DefaultClock = clockwork.NewRealClock()
)

func (a *Server) CreateVertiportSubscription(ctx context.Context, req *vrppb.CreateVertiportSubscriptionRequest) (*vrppb.PutVertiportSubscriptionResponse, error) {
	return a.PutVertiportSubscription(ctx, req.GetSubscriptionid(), "", req.GetParams())
}

func (a *Server) UpdateVertiportSubscription(ctx context.Context, req *vrppb.UpdateVertiportSubscriptionRequest) (*vrppb.PutVertiportSubscriptionResponse, error) {
	version := req.GetVersion()
	return a.PutVertiportSubscription(ctx, req.GetSubscriptionid(), version, req.GetParams())
}

// PutSubscription creates a single subscription.
func (a *Server) PutVertiportSubscription(ctx context.Context, subscriptionid string, version string, params *vrppb.PutVertiportSubscriptionParameters) (*vrppb.PutVertiportSubscriptionResponse, error) {
	// Retrieve VertiportSubscription ID
	id, err := dssmodels.IDFromString(subscriptionid)

	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", subscriptionid)
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing owner from context")
	}

	if !a.EnableHTTP {
		err = scdmodels.ValidateUSSBaseURL(params.UssBaseUrl)
		if err != nil {
			return nil, stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Failed to validate base URL")
		}
	}

	vertiportReservation, err := dssmodels.VertiportReservationFromVRPProto(params.VertiportReservation)

	subreq := &vrpmodels.VertiportSubscription{
		ID:      id,
		Manager: manager,
		Version: vrpmodels.OVN(version),

		StartTime:     vertiportReservation.StartTime,
		EndTime:       vertiportReservation.EndTime,
		VertiportID:   vertiportReservation.VertiportID,
		VertiportZone: vertiportReservation.VertiportZone,

		USSBaseURL:                  params.UssBaseUrl,
		NotifyForOperationalIntents: params.NotifyForOperationalIntents,
		NotifyForConstraints:        params.NotifyForConstraints,
	}

	// Validate requested VertiportSubscription
	if !subreq.NotifyForOperationalIntents && !subreq.NotifyForConstraints {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "No notification triggers requested for VertiportSubscription")
	}

	var result *vrppb.PutVertiportSubscriptionResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Check existing VertiportSubscription (if any)
		old, err := r.GetVertiportSubscription(ctx, subreq.ID)
		if err != nil {
			return stacktrace.Propagate(err, "Could not get VertiportSubscription from repo")
		}

		// Validate and perhaps correct StartTime and EndTime.
		if err := subreq.AdjustTimeRange(DefaultClock.Now(), old); err != nil {
			return stacktrace.Propagate(err, "Error adjusting time range of VertiportSubscription")
		}

		var dependentOpIds []dssmodels.ID

		if old == nil {
			// There is no previous VertiportSubscription (this is a creation attempt)
			if subreq.Version.String() != "" {
				// The user wants to update an existing VertiportSubscription, but one wasn't found.
				return stacktrace.NewErrorWithCode(dsserr.NotFound, "VertiportSubscription %s not found", subreq.ID.String())
			}
		} else {
			// There is a previous VertiportSubscription (this is an update attempt)
			switch {
			case subreq.Version.String() == "":
				// The user wants to create a new VertiportSubscription but it already exists.
				return stacktrace.NewErrorWithCode(dsserr.AlreadyExists, "VertiportSubscription %s already exists", subreq.ID.String())
			case subreq.Version.String() != old.Version.String():
				// The user wants to update a VertiportSubscription but the version doesn't match.
				return stacktrace.Propagate(
					stacktrace.NewErrorWithCode(dsserr.VersionMismatch, "VertiportSubscription version %s is not current", subreq.Version),
					"Current version is %s but client specified version %s", old.Version, subreq.Version)
			case old.Manager != subreq.Manager:
				return stacktrace.Propagate(
					stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "VertiportSubscription is owned by different client"),
					"VertiportSubscription owned by %s, but %s attempted to modify", old.Manager, subreq.Manager)
			}

			subreq.NotificationIndex = old.NotificationIndex

			// Validate VertiportSubscription against DependentOperations
			dependentOpIds, err = r.GetDependentVertiportOperationalIntents(ctx, subreq.ID)
			if err != nil {
				return stacktrace.Propagate(err, "Could not find dependent Operation Ids")
			}

			operations, err := GetVertiportOperations(ctx, r, dependentOpIds)
			if err != nil {
				return stacktrace.Propagate(err, "Could not get all dependent Operations")
			}
			if err := subreq.ValidateDependentOps(operations); err != nil {
				// The provided subscription does not cover all its dependent operations
				return err
			}
		}

		// Store VertiportSubscription model
		sub, err := r.UpsertVertiportSubscription(ctx, subreq)
		if err != nil {
			return stacktrace.Propagate(err, "Could not upsert VertiportSubscription into repo")
		}
		if sub == nil {
			return stacktrace.NewError("UpsertSubscription returned no VertiportSubscription for ID: %s", id)
		}

		// Find relevant Operations
		var relevantOperations []*vrpmodels.VertiportOperationalIntent
		if len(sub.VertiportID) > 0 {
			ops, err := r.SearchVertiportOperationalIntents(ctx, &dssmodels.VertiportReservation{
				VertiportID:   sub.VertiportID,
				VertiportZone: sub.VertiportZone,
				StartTime:     sub.StartTime,
				EndTime:       sub.EndTime,
			})
			if err != nil {
				return stacktrace.Propagate(err, "Could not search Operations in repo")
			}
			relevantOperations = ops
		}

		// Convert VertiportSubscription to proto
		p, err := sub.ToProto(dependentOpIds)
		if err != nil {
			return stacktrace.Propagate(err, "Could not convert VertiportSubscription to proto")
		}
		result = &vrppb.PutVertiportSubscriptionResponse{
			Subscription: p,
		}

		if sub.NotifyForOperationalIntents {
			// Attach Operations to response
			for _, op := range relevantOperations {
				if op.Manager != manager {
					op.OVN = vrpmodels.OVN(vrpmodels.NoOvnPhrase)
				}
				pop, _ := op.ToProto()
				result.OperationalIntentReferences = append(result.OperationalIntentReferences, pop)
			}
		}

		if sub.NotifyForConstraints {
			// Query relevant Constraints
			constraints, err := r.SearchVertiportConstraints(ctx, vertiportReservation)
			if err != nil {
				return stacktrace.Propagate(err, "Could not search Constraints in repo")
			}

			// Attach Constraints to response
			for _, constraint := range constraints {
				p, err := constraint.ToProto()
				if err != nil {
					return stacktrace.Propagate(err, "Could not convert Constraint to proto")
				}
				if constraint.Manager != manager {
					p.Ovn = vrpmodels.NoOvnPhrase
				}
				result.ConstraintReferences = append(result.ConstraintReferences, p)
			}
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	// Return response to client
	return result, nil
}

// GetSubscription returns a single subscription for the given ID.
func (a *Server) GetVertiportSubscription(ctx context.Context, req *vrppb.GetVertiportSubscriptionRequest) (*vrppb.GetVertiportSubscriptionResponse, error) {
	// Retrieve VertiportSubscription ID
	id, err := dssmodels.IDFromString(req.GetSubscriptionid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetSubscriptionid())
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing owner from context")
	}

	var response *vrppb.GetVertiportSubscriptionResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Get VertiportSubscription from Store
		sub, err := r.GetVertiportSubscription(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Could not get VertiportSubscription from repo")
		}
		if sub == nil {
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "VertiportSubscription %s not found", id.String())
		}

		// Check if the client is authorized to view this VertiportSubscription
		if manager != sub.Manager {
			return stacktrace.Propagate(
				stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "VertiportSubscription is owned by different client"),
				"VertiportSubscription owned by %s, but %s attempted to view", sub.Manager, manager)
		}

		// Get dependent Operations
		dependentOps, err := r.GetDependentVertiportOperationalIntents(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Could not find dependent Operations")
		}

		// Convert VertiportSubscription to proto
		p, err := sub.ToProto(dependentOps)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to convert VertiportSubscription to proto")
		}

		// Return response to client
		response = &vrppb.GetVertiportSubscriptionResponse{
			Subscription: p,
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// QuerySubscriptions queries existing subscriptions in the given bounds.
func (a *Server) QueryVertiportSubscriptions(ctx context.Context, req *vrppb.QueryVertiportSubscriptionsRequest) (*vrppb.QueryVertiportSubscriptionsResponse, error) {
	// Retrieve the vertiport reservation of interest parameter
	vroi := req.GetParams().VertiportReservationOfInterest
	
	if vroi == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing vertiport_reservation_of_interest")
	}

	reservation, err := dssmodels.VertiportReservationFromVRPProto(vroi)
	if err != nil {
		return nil, stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Failed to convert to internal geometry model")
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing owner from context")
	}

	var response *vrppb.QueryVertiportSubscriptionsResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Perform search query on Store
		subs, err := r.SearchVertiportSubscriptions(ctx, reservation)
		if err != nil {
			return stacktrace.Propagate(err, "Error searching Subscriptions in repo")
		}

		// Return response to client
		response = &vrppb.QueryVertiportSubscriptionsResponse{}
		for _, sub := range subs {
			if sub.Manager == manager {
				// Get dependent Operations
				dependentOps, err := r.GetDependentVertiportOperationalIntents(ctx, sub.ID)
				if err != nil {
					return stacktrace.Propagate(err, "Could not find dependent Operations")
				}

				p, err := sub.ToProto(dependentOps)
				if err != nil {
					return stacktrace.Propagate(err, "Error converting VertiportSubscription model to proto")
				}
				response.Subscriptions = append(response.Subscriptions, p)
			}
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// DeleteSubscription deletes a single subscription for a given ID.
func (a *Server) DeleteVertiportSubscription(ctx context.Context, req *vrppb.DeleteVertiportSubscriptionRequest) (*vrppb.DeleteVertiportSubscriptionResponse, error) {
	// Retrieve VertiportSubscription ID
	id, err := dssmodels.IDFromString(req.GetSubscriptionid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format")
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing owner from context")
	}

	var response *vrppb.DeleteVertiportSubscriptionResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Check to make sure it's ok to delete this VertiportSubscription
		old, err := r.GetVertiportSubscription(ctx, id)
		switch {
		case err != nil:
			return stacktrace.Propagate(err, "Could not get VertiportSubscription from repo")
		case old == nil: // Return a 404 here.
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "VertiportSubscription %s not found", id.String())
		case old.Manager != manager:
			return stacktrace.Propagate(
				stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "VertiportSubscription is owned by different client"),
				"VertiportSubscription owned by %s, but %s attempted to delete", old.Manager, manager)
		}

		// Get dependent Operations
		dependentOps, err := r.GetDependentVertiportOperationalIntents(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Could not find dependent Operations")
		}
		if len(dependentOps) > 0 {
			return stacktrace.Propagate(
				stacktrace.NewErrorWithCode(dsserr.BadRequest, "Subscriptions with dependent Operations may not be removed"),
				"VertiportSubscription had %d dependent Operations", len(dependentOps))
		}

		// Delete VertiportSubscription in repo
		err = r.DeleteVertiportSubscription(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Could not delete VertiportSubscription from repo")
		}

		// Convert deleted VertiportSubscription to proto
		p, err := old.ToProto(dependentOps)
		if err != nil {
			return stacktrace.Propagate(err, "Error converting VertiportSubscription model to proto")
		}

		// Create response for client
		response = &vrppb.DeleteVertiportSubscriptionResponse{
			Subscription: p,
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// GetOperations gets operations by given ids
func GetVertiportOperations(ctx context.Context, r repos.Repository, opIDs []dssmodels.ID) ([]*vrpmodels.VertiportOperationalIntent, error) {
	var res []*vrpmodels.VertiportOperationalIntent
	for _, opID := range opIDs {
		operation, err := r.GetVertiportOperationalIntent(ctx, opID)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Could not retrieve dependent Operation %s", opID)
		}
		res = append(res, operation)
	}
	return res, nil
}
