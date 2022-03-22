package vrp

import (
	"context"

	"github.com/interuss/dss/pkg/api/v1/vrppb"
	"github.com/interuss/dss/pkg/auth"
	dsserr "github.com/interuss/dss/pkg/errors"
	dssmodels "github.com/interuss/dss/pkg/models"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/interuss/dss/pkg/vrp/repos"
	"github.com/interuss/stacktrace"
	"github.com/jackc/pgx/v4"
)

// DeleteConstraintReference deletes a single constraint ref for a given ID at
// the specified version.
func (a *Server) DeleteVertiportConstraintReference(ctx context.Context, req *vrppb.DeleteVertiportConstraintReferenceRequest) (*vrppb.ChangeVertiportConstraintReferenceResponse, error) {
	// Retrieve Constraint ID
	id, err := dssmodels.IDFromString(req.GetEntityid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetEntityid())
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	var response *vrppb.ChangeVertiportConstraintReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Make sure deletion request is valid
		old, err := r.GetVertiportConstraint(ctx, id)
		switch {
		case err == pgx.ErrNoRows:
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "Constraint %s not found", id.String())
		case err != nil:
			return stacktrace.Propagate(err, "Unable to get Constraint from repo")
		case old.Manager != manager:
			return stacktrace.NewErrorWithCode(dsserr.PermissionDenied,
				"Constraint owned by %s, but %s attempted to delete", old.Manager, manager)
		}

		// Find Subscriptions that may overlap the Constraint's Volume4D
		allsubs, err := r.SearchVertiportSubscriptions(ctx, &dssmodels.VertiportReservation{
			StartTime:     old.StartTime,
			EndTime:       old.EndTime,
			VertiportID:   old.VertiportID,
			VertiportZone: old.VertiportZone,
		})
		if err != nil {
			return stacktrace.Propagate(err, "Unable to search Subscriptions in repo")
		}

		// Limit Subscription notifications to only those interested in Constraints
		var subs repos.VertiportSubscriptions
		for _, sub := range allsubs {
			if sub.NotifyForConstraints {
				subs = append(subs, sub)
			}
		}

		// Delete Constraint in repo
		err = r.DeleteVertiportConstraint(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to delete Constraint from repo")
		}

		// Increment notification indices for relevant Subscriptions
		err = subs.IncrementNotificationIndices(ctx, r)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to increment notification indices")
		}

		// Convert deleted Constraint to proto
		constraintProto, err := old.ToProto()
		if err != nil {
			return stacktrace.Propagate(err, "Could not convert Constraint to proto")
		}

		// Return response to client
		response = &vrppb.ChangeVertiportConstraintReferenceResponse{
			ConstraintReference: constraintProto,
			Subscribers:         makeSubscribersToNotify(subs),
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// GetConstraintReference returns a single constraint ref for the given ID.
func (a *Server) GetVertiportConstraintReference(ctx context.Context, req *vrppb.GetVertiportConstraintReferenceRequest) (*vrppb.GetVertiportConstraintReferenceResponse, error) {
	id, err := dssmodels.IDFromString(req.GetEntityid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetEntityid())
	}

	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	var response *vrppb.GetVertiportConstraintReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		constraint, err := r.GetVertiportConstraint(ctx, id)
		switch {
		case err == pgx.ErrNoRows:
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "Constraint %s not found", id.String())
		case err != nil:
			return stacktrace.Propagate(err, "Unable to get Constraint from repo")
		}

		if constraint.Manager != manager {
			constraint.OVN = vrpmodels.OVN(vrpmodels.NoOvnPhrase)
		}

		// Convert retrieved Constraint to proto
		p, err := constraint.ToProto()
		if err != nil {
			return stacktrace.Propagate(err, "Could not convert Constraint to proto")
		}

		// Return response to client
		response = &vrppb.GetVertiportConstraintReferenceResponse{
			ConstraintReference: p,
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

func (a *Server) CreateVertiportConstraintReference(ctx context.Context, req *vrppb.CreateVertiportConstraintReferenceRequest) (*vrppb.ChangeVertiportConstraintReferenceResponse, error) {
	return a.PutVertiportConstraintReference(ctx, req.GetEntityid(), "", req.GetParams())
}

func (a *Server) UpdateVertiportConstraintReference(ctx context.Context, req *vrppb.UpdateVertiportConstraintReferenceRequest) (*vrppb.ChangeVertiportConstraintReferenceResponse, error) {
	return a.PutVertiportConstraintReference(ctx, req.GetEntityid(), req.GetOvn(), req.GetParams())
}

// PutConstraintReference inserts or updates a Constraint.
// If the ovn argument is empty (""), it will attempt to create a new Constraint.
func (a *Server) PutVertiportConstraintReference(ctx context.Context, entityid string, ovn string, params *vrppb.PutVertiportConstraintReferenceParameters) (*vrppb.ChangeVertiportConstraintReferenceResponse, error) {
	id, err := dssmodels.IDFromString(entityid)

	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", entityid)
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	if len(params.UssBaseUrl) == 0 {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing required UssBaseUrl")
	}

	if !a.EnableHTTP {
		err = vrpmodels.ValidateUSSBaseURL(params.UssBaseUrl)
		if err != nil {
			return nil, stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Failed to validate base URL")
		}
	}

	extent := params.GetVertiportReservation()
	uExtent, err := dssmodels.VertiportReservationFromVRPProto(extent)
	if err != nil {
		return nil, stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Failed to parse vertiport reservation")
	}

	if uExtent.StartTime == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing time_start from extents")
	}
	if uExtent.EndTime == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing time_end from extents")
	}

	var response *vrppb.ChangeVertiportConstraintReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		var version int32 // Version of the Constraint (0 means creation requested).

		// Get existing Constraint, if any, and validate request
		old, err := r.GetVertiportConstraint(ctx, id)
		switch {
		case err == pgx.ErrNoRows:
			// No existing Constraint; verify that creation was requested
			if ovn != "" {
				return stacktrace.NewErrorWithCode(dsserr.VersionMismatch, "Old version %s does not exist", ovn)
			}
			version = 0
		case err != nil:
			return stacktrace.Propagate(err, "Could not get Constraint from repo")
		}
		if old != nil {
			if old.Manager != manager {
				return stacktrace.NewErrorWithCode(dsserr.PermissionDenied,
					"Constraint owned by %s, but %s attempted to modify", old.Manager, manager)
			}
			if old.OVN != vrpmodels.OVN(ovn) {
				return stacktrace.NewErrorWithCode(dsserr.VersionMismatch,
					"Current version is %s but client specified version %s", old.OVN, ovn)
			}
			version = int32(old.Version)
		}

		var notifyVol4 *dssmodels.VertiportReservation
		notifyVol4 = uExtent

		// Upsert the Constraint
		constraint, err := r.UpsertVertiportConstraint(ctx, &vrpmodels.VertiportConstraint{
			ID:      id,
			Manager: manager,
			Version: vrpmodels.VersionNumber(version + 1),

			StartTime:     uExtent.StartTime,
			EndTime:       uExtent.EndTime,
			VertiportZone: uExtent.VertiportZone,
			VertiportID:   uExtent.VertiportID,

			USSBaseURL: params.UssBaseUrl,
		})
		if err != nil {
			return err
		}

		// Find Subscriptions that may need to be notified
		allsubs, err := r.SearchVertiportSubscriptions(ctx, notifyVol4)
		if err != nil {
			return err
		}

		// Limit Subscription notifications to only those interested in Constraints
		var subs repos.VertiportSubscriptions
		for _, sub := range allsubs {
			if sub.NotifyForConstraints {
				subs = append(subs, sub)
			}
		}

		// Increment notification indices for relevant Subscriptions
		err = subs.IncrementNotificationIndices(ctx, r)
		if err != nil {
			return err
		}

		// Convert upserted Constraint to proto
		p, err := constraint.ToProto()
		if err != nil {
			return err
		}

		// Return response to client
		response = &vrppb.ChangeVertiportConstraintReferenceResponse{
			ConstraintReference: p,
			Subscribers:         makeSubscribersToNotify(subs),
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// QueryConstraintReferences queries existing contraint refs in the given
// bounds.
func (a *Server) QueryVertiportConstraintReferences(ctx context.Context, req *vrppb.QueryVertiportConstraintReferencesRequest) (*vrppb.QueryVertiportConstraintReferencesResponse, error) {
	// Retrieve the area of interest parameter
	aoi := req.GetParams().ReservationOfInterest
	if aoi == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing area_of_interest")
	}

	// Parse area of interest to common Volume4D
	vol4, err := dssmodels.VertiportReservationFromVRPProto(aoi)
	if err != nil {
		return nil, err
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	var response *vrppb.QueryVertiportConstraintReferencesResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Perform search query on Store
		constraints, err := r.SearchVertiportConstraints(ctx, vol4)
		if err != nil {
			return err
		}

		// Create response for client
		response = &vrppb.QueryVertiportConstraintReferencesResponse{}
		for _, constraint := range constraints {
			p, err := constraint.ToProto()
			if err != nil {
				return err
			}
			if constraint.Manager != manager {
				p.Ovn = vrpmodels.NoOvnPhrase
			}
			response.ConstraintReferences = append(response.ConstraintReferences, p)
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}
