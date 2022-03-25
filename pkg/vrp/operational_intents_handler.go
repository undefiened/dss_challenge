package vrp

import (
	"context"
	"github.com/golang/protobuf/ptypes"
	"time"

	"github.com/google/uuid"
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	"github.com/interuss/dss/pkg/auth"
	dsserr "github.com/interuss/dss/pkg/errors"
	dssmodels "github.com/interuss/dss/pkg/models"
	vrperr "github.com/interuss/dss/pkg/vrp/errors"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/interuss/dss/pkg/vrp/repos"
	"github.com/interuss/stacktrace"
	"google.golang.org/grpc/status"
)

// DeleteOperationalIntentReference deletes a single operational intent ref for a given ID at
// the specified version.
func (a *Server) DeleteVertiportOperationalIntentReference(ctx context.Context, req *vrppb.DeleteVertiportOperationalIntentReferenceRequest) (*vrppb.ChangeVertiportOperationalIntentReferenceResponse, error) {
	// Retrieve OperationalIntent ID
	id, err := dssmodels.IDFromString(req.GetEntityid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetEntityid())
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	var response *vrppb.ChangeVertiportOperationalIntentReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Get OperationalIntent to delete
		old, err := r.GetVertiportOperationalIntent(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to get OperationIntent from repo")
		}
		if old == nil {
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "OperationalIntent %s not found", id)
		}

		// Validate deletion request
		if old.Manager != manager {
			return stacktrace.NewErrorWithCode(dsserr.PermissionDenied,
				"OperationalIntent owned by %s, but %s attempted to delete", old.Manager, manager)
		}

		// Get the Subscription supporting the OperationalIntent
		sub, err := r.GetVertiportSubscription(ctx, old.SubscriptionID)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to get OperationalIntent's Subscription from repo")
		}
		if sub == nil {
			return stacktrace.NewError("OperationalIntent's Subscription missing from repo")
		}

		removeImplicitSubscription := false
		if sub.ImplicitSubscription {
			// Get the Subscription's dependent OperationalIntents
			dependentOps, err := r.GetDependentVertiportOperationalIntents(ctx, sub.ID)
			if err != nil {
				return stacktrace.Propagate(err, "Could not find dependent OperationalIntents")
			}
			if len(dependentOps) == 0 {
				return stacktrace.NewError("An implicit Subscription had no dependent OperationalIntents")
			} else if len(dependentOps) == 1 {
				removeImplicitSubscription = true
			}
		}

		allsubs, err := r.SearchVertiportSubscriptions(ctx, &dssmodels.VertiportReservation{
			StartTime:     old.StartTime,
			EndTime:       old.EndTime,
			VertiportID:   old.VertiportID,
			VertiportZone: old.VertiportZone,
		})
		if err != nil {
			return stacktrace.Propagate(err, "Unable to search Subscriptions in repo")
		}

		// Limit Subscription notifications to only those interested in OperationalIntents
		var subs repos.VertiportSubscriptions
		for _, s := range allsubs {
			if s.NotifyForOperationalIntents {
				subs = append(subs, s)
			}
		}

		// Increment notification indices for Subscriptions to be notified
		if err := subs.IncrementNotificationIndices(ctx, r); err != nil {
			return stacktrace.Propagate(err, "Unable to increment notification indices")
		}

		// Delete OperationalIntent from repo
		if err := r.DeleteVertiportOperationalIntent(ctx, id); err != nil {
			return stacktrace.Propagate(err, "Unable to delete OperationalIntent from repo")
		}

		if removeImplicitSubscription {
			// Automatically remove a now-unused implicit Subscription
			err = r.DeleteVertiportSubscription(ctx, sub.ID)
			if err != nil {
				return stacktrace.Propagate(err, "Unable to delete associated implicit Subscription")
			}
		}

		// Convert deleted OperationalIntent to proto
		opProto, err := old.ToProto()
		if err != nil {
			return stacktrace.Propagate(err, "Could not convert OperationalIntent to proto")
		}

		// Return response to client
		response = &vrppb.ChangeVertiportOperationalIntentReferenceResponse{
			OperationalIntentReference: opProto,
			Subscribers:                makeSubscribersToNotify(subs),
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// GetOperationalIntentReference returns a single operation intent ref for the given ID.
func (a *Server) GetVertiportOperationalIntentReference(ctx context.Context, req *vrppb.GetVertiportOperationalIntentReferenceRequest) (*vrppb.GetVertiportOperationalIntentReferenceResponse, error) {
	id, err := dssmodels.IDFromString(req.GetEntityid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetEntityid())
	}

	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	var response *vrppb.GetVertiportOperationalIntentReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		op, err := r.GetVertiportOperationalIntent(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to get OperationalIntent from repo")
		}
		if op == nil {
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "OperationalIntent %s not found", id)
		}

		if op.Manager != manager {
			op.OVN = vrpmodels.OVN(vrpmodels.NoOvnPhrase)
		}

		p, err := op.ToProto()
		if err != nil {
			return stacktrace.Propagate(err, "Could not convert OperationalIntent to proto")
		}

		response = &vrppb.GetVertiportOperationalIntentReferenceResponse{
			OperationalIntentReference: p,
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

// QueryOperationalIntentsReferences queries existing operational intent refs in the given
// bounds.
func (a *Server) QueryVertiportOperationalIntentReferences(ctx context.Context, req *vrppb.QueryVertiportOperationalIntentReferencesRequest) (*vrppb.QueryVertiportOperationalIntentReferenceResponse, error) {
	// Retrieve the area of interest parameter
	aoi := req.GetParams().GetVertiportReservationOfInterest()
	if aoi == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing vertiport reservation")
	}

	// Parse area of interest to common Volume4D
	vol4, err := dssmodels.VertiportReservationFromVRPProto(aoi)
	if err != nil {
		return nil, stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Error parsing geometry")
	}

	// Retrieve ID of client making call
	manager, ok := auth.ManagerFromContext(ctx)
	if !ok {
		return nil, stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Missing manager from context")
	}

	var response *vrppb.QueryVertiportOperationalIntentReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Perform search query on Store
		ops, err := r.SearchVertiportOperationalIntents(ctx, vol4)
		if err != nil {
			return stacktrace.Propagate(err, "Unable to query for OperationalIntents in repo")
		}

		// Create response for client
		response = &vrppb.QueryVertiportOperationalIntentReferenceResponse{}
		for _, op := range ops {
			p, err := op.ToProto()
			if err != nil {
				return stacktrace.Propagate(err, "Could not convert OperationalIntent model to proto")
			}
			if op.Manager != manager {
				p.Ovn = vrpmodels.NoOvnPhrase
			}
			response.OperationalIntentReferences = append(response.OperationalIntentReferences, p)
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

func (a *Server) CreateVertiportOperationalIntentReference(ctx context.Context, req *vrppb.CreateVertiportOperationalIntentReferenceRequest) (*vrppb.ChangeVertiportOperationalIntentReferenceResponse, error) {
	return a.PutVertiportOperationalIntentReference(ctx, req.GetEntityid(), "", req.GetParams())
}

func (a *Server) UpdateVertiportOperationalIntentReference(ctx context.Context, req *vrppb.UpdateVertiportOperationalIntentReferenceRequest) (*vrppb.ChangeVertiportOperationalIntentReferenceResponse, error) {
	return a.PutVertiportOperationalIntentReference(ctx, req.GetEntityid(), req.Ovn, req.GetParams())
}

// PutOperationalIntentReference inserts or updates an Operational Intent.
// If the ovn argument is empty (""), it will attempt to create a new Operational Intent.
func (a *Server) PutVertiportOperationalIntentReference(ctx context.Context, entityid string, ovn string, params *vrppb.PutVertiportOperationalIntentReferenceParameters) (*vrppb.ChangeVertiportOperationalIntentReferenceResponse, error) {
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

	state := vrpmodels.OperationalIntentState(params.State)
	if !state.IsValidInDSS() {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid OperationalIntent state: %s", params.State)
	}

	reservation := params.GetVertiportReservation()
	uExtent, err := dssmodels.VertiportReservationFromVRPProto(reservation)
	if err != nil {
		return nil, stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Failed to parse extent")
	}

	if uExtent.StartTime == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing time_start from extents")
	}
	if uExtent.EndTime == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing time_end from extents")
	}

	if time.Now().After(*uExtent.EndTime) {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "OperationalIntents may not end in the past")
	}

	if uExtent.EndTime.Before(*uExtent.StartTime) {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "End time is past the start time")
	}

	if ovn == "" && params.State != "Accepted" {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid state for initial version: `%s`", params.State)
	}

	subscriptionID, err := dssmodels.IDFromOptionalString(params.GetSubscriptionId())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format for Subscription ID: `%s`", params.GetSubscriptionId())
	}

	var response *vrppb.ChangeVertiportOperationalIntentReferenceResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		var version int32 // Version of the Operational Intent (0 means creation requested).

		// Get existing OperationalIntent, if any, and validate request
		old, err := r.GetVertiportOperationalIntent(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Could not get OperationalIntent from repo")
		}
		if old != nil {
			if old.Manager != manager {
				return stacktrace.NewErrorWithCode(dsserr.PermissionDenied,
					"OperationalIntent owned by %s, but %s attempted to modify", old.Manager, manager)
			}
			if old.OVN != vrpmodels.OVN(ovn) {
				return stacktrace.NewErrorWithCode(dsserr.VersionMismatch,
					"Current version is %s but client specified version %s", old.OVN, ovn)
			}

			version = int32(old.Version)
		} else {
			if ovn != "" {
				return stacktrace.NewErrorWithCode(dsserr.NotFound, "OperationalIntent does not exist and therefore is not version %s", ovn)
			}

			version = 0
		}

		var sub *vrpmodels.VertiportSubscription
		if subscriptionID.Empty() {
			// Create implicit Subscription
			subBaseURL := params.GetNewSubscription().GetUssBaseUrl()
			if subBaseURL == "" {
				return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Missing uss_base_url in new_subscription")
			}
			if !a.EnableHTTP {
				err := vrpmodels.ValidateUSSBaseURL(subBaseURL)
				if err != nil {
					return stacktrace.PropagateWithCode(err, dsserr.BadRequest, "Failed to validate USS base URL")
				}
			}

			sub, err = r.UpsertVertiportSubscription(ctx, &vrpmodels.VertiportSubscription{
				ID:                          dssmodels.ID(uuid.New().String()),
				Manager:                     manager,
				StartTime:                   uExtent.StartTime,
				EndTime:                     uExtent.EndTime,
				VertiportID:                 uExtent.VertiportID,
				VertiportZone:               uExtent.VertiportZone,
				USSBaseURL:                  subBaseURL,
				NotifyForOperationalIntents: true,
				NotifyForConstraints:        params.GetNewSubscription().GetNotifyForConstraints(),
				ImplicitSubscription:        true,
			})
			if err != nil {
				return stacktrace.Propagate(err, "Failed to create implicit subscription")
			}
		} else {
			// Use existing Subscription
			sub, err = r.GetVertiportSubscription(ctx, subscriptionID)
			if err != nil {
				return stacktrace.Propagate(err, "Unable to get Subscription")
			}
			if sub == nil {
				return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Specified Subscription %s does not exist", subscriptionID)
			}
			if sub.Manager != manager {
				return stacktrace.Propagate(
					stacktrace.NewErrorWithCode(dsserr.PermissionDenied, "Specificed Subscription is owned by different client"),
					"Subscription %s owned by %s, but %s attempted to use it for an OperationalIntent", subscriptionID, sub.Manager, manager)
			}
			updateSub := false
			if sub.StartTime != nil && sub.StartTime.After(*uExtent.StartTime) {
				if sub.ImplicitSubscription {
					sub.StartTime = uExtent.StartTime
					updateSub = true
				} else {
					return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Subscription does not begin until after the OperationalIntent starts")
				}
			}
			if sub.EndTime != nil && sub.EndTime.Before(*uExtent.EndTime) {
				if sub.ImplicitSubscription {
					sub.EndTime = uExtent.EndTime
					updateSub = true
				} else {
					return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Subscription ends before the OperationalIntent ends")
				}
			}
			if sub.VertiportID != uExtent.VertiportID {
				if sub.ImplicitSubscription {
					sub.VertiportID = uExtent.VertiportID
					updateSub = true
				} else {
					return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Subscription does not cover the same vertiport than the OperationalIntent")
				}
			}

			if sub.VertiportZone != uExtent.VertiportZone {
				if sub.ImplicitSubscription {
					sub.VertiportZone = uExtent.VertiportZone
					updateSub = true
				} else {
					return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Subscription does not cover the same vertiport zone than the OperationalIntent")
				}
			}

			if updateSub {
				sub, err = r.UpsertVertiportSubscription(ctx, sub)
				if err != nil {
					return stacktrace.Propagate(err, "Failed to update existing Subscription")
				}
			}
		}

		if state.RequiresKey() {
			// Construct a hash set of OVNs as the key
			key := map[vrpmodels.OVN]bool{}
			for _, ovn := range params.GetKey() {
				key[vrpmodels.OVN(ovn)] = true
			}

			// Identify OperationalIntents missing from the key
			var missingOps []*vrpmodels.VertiportOperationalIntent
			relevantOps, err := r.SearchVertiportOperationalIntents(ctx, uExtent)
			if err != nil {
				return stacktrace.Propagate(err, "Unable to SearchOperations")
			}
			for _, relevantOp := range relevantOps {
				if _, ok := key[relevantOp.OVN]; !ok {
					if relevantOp.Manager != manager {
						relevantOp.OVN = vrpmodels.NoOvnPhrase
					}
					missingOps = append(missingOps, relevantOp)
				}
			}

			// Identify Constraints missing from the key
			var missingConstraints []*vrpmodels.VertiportConstraint
			if sub.NotifyForConstraints {
				constraints, err := r.SearchVertiportConstraints(ctx, uExtent)
				if err != nil {
					return stacktrace.Propagate(err, "Unable to SearchConstraints")
				}
				for _, relevantConstraint := range constraints {
					if _, ok := key[relevantConstraint.OVN]; !ok {
						if relevantConstraint.Manager != manager {
							relevantConstraint.OVN = vrpmodels.NoOvnPhrase
						}
						missingConstraints = append(missingConstraints, relevantConstraint)
					}
				}
			}

			// If the client is missing some OVNs, provide the pointers to the
			// information they need
			if len(missingOps) > 0 || len(missingConstraints) > 0 {
				p, err := vrperr.MissingOVNsErrorResponse(missingOps, missingConstraints)
				if err != nil {
					return stacktrace.Propagate(err, "Failed to construct missing OVNs error message")
				}
				return stacktrace.Propagate(status.ErrorProto(p), "Missing OVNs")
			}
		}

		// Construct the new OperationalIntent
		op := &vrpmodels.VertiportOperationalIntent{
			ID:      id,
			Manager: manager,
			Version: vrpmodels.VersionNumber(version + 1),

			StartTime:     uExtent.StartTime,
			EndTime:       uExtent.EndTime,
			VertiportID:   uExtent.VertiportID,
			VertiportZone: uExtent.VertiportZone,

			USSBaseURL:     params.UssBaseUrl,
			SubscriptionID: sub.ID,
			State:          state,
		}
		err = op.ValidateTimeRange()
		if err != nil {
			return stacktrace.Propagate(err, "Error validating time range")
		}

		// Compute total affected Volume4D for notification purposes
		//var notifyVol4 *dssmodels.VertiportReservation
		//if old == nil {
		//	notifyVol4 = uExtent
		//} else {
		//	oldVol4 := &dssmodels.VertiportReservation{
		//		StartTime: old.StartTime,
		//		EndTime:   old.EndTime,
		//        VertiportID: old.VertiportID,
		//        VertiportZone: old.VertiportZone,
		//		}}
		//	notifyVol4, err = dssmodels.UnionVolumes4D(uExtent, oldVol4)
		//	if err != nil {
		//		return stacktrace.Propagate(err, "Error constructing 4D volumes union")
		//	}
		//}

		// Upsert the OperationalIntent
		op, err = r.UpsertVertiportOperationalIntent(ctx, op)
		if err != nil {
			return stacktrace.Propagate(err, "Failed to upsert OperationalIntent in repo")
		}

		// Find Subscriptions that may need to be notified
		allsubs, err := r.SearchVertiportSubscriptions(ctx, uExtent)
		if err != nil {
			return err
		}

		// Limit Subscription notifications to only those interested in OperationalIntents
		var subs repos.VertiportSubscriptions
		for _, sub := range allsubs {
			if sub.NotifyForOperationalIntents {
				subs = append(subs, sub)
			}
		}

		// Increment notification indices for relevant Subscriptions
		err = subs.IncrementNotificationIndices(ctx, r)
		if err != nil {
			return err
		}

		// Convert upserted OperationalIntent to proto
		p, err := op.ToProto()
		if err != nil {
			return stacktrace.Propagate(err, "Could not convert OperationalIntent to proto")
		}

		// Return response to client
		response = &vrppb.ChangeVertiportOperationalIntentReferenceResponse{
			OperationalIntentReference: p,
			Subscribers:                makeSubscribersToNotify(subs),
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

func (a *Server) GetNumberOfUsedParkingPlaces(ctx context.Context, req *vrppb.GetNumberOfUsedParkingPlacesRequest) (*vrppb.GetNumberOfUsedParkingPlacesResponse, error) {
	id, err := dssmodels.IDFromString(req.GetVertiportid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetVertiportid())
	}

	if req.GetTimeStart() == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Start time is missing")
	}

	if req.GetTimeEnd() == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "End time is missing")
	}

	st := req.GetTimeStart().GetValue()
	startTime, err := ptypes.Timestamp(st)
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Error converting start time from proto")
	}

	et := req.GetTimeStart().GetValue()
	endTime, err := ptypes.Timestamp(et)
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Error converting end time from proto")
	}

	var response *vrppb.GetNumberOfUsedParkingPlacesResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		vertiport, err := r.GetVertiport(ctx, id)

		if err != nil {
			return stacktrace.Propagate(err, "Could not find Vertiport")
		}

		var numberOfUsedPlaces int32 = 0

		constraints, err := r.SearchVertiportConstraints(ctx, &dssmodels.VertiportReservation{
			VertiportID:   id,
			VertiportZone: dssmodels.ParkingStand,
			StartTime:     &startTime,
			EndTime:       &endTime,
		})

		if err != nil {
			return stacktrace.Propagate(err, "Error finding related vertiport constraints")
		}

		numberOfUsedPlaces = numberOfUsedPlaces + int32(len(constraints))

		operationalIntents, err := r.SearchVertiportOperationalIntents(ctx, &dssmodels.VertiportReservation{
			VertiportID:   id,
			VertiportZone: dssmodels.ParkingStand,
			StartTime:     &startTime,
			EndTime:       &endTime,
		})

		numberOfUsedPlaces = numberOfUsedPlaces + int32(len(operationalIntents))

		if err != nil {
			return stacktrace.Propagate(err, "Error finding related vertiport constraints")
		}

		response = &vrppb.GetNumberOfUsedParkingPlacesResponse{
			NumberOfUsedPlaces:      numberOfUsedPlaces,
			NumberOfAvailablePlaces: vertiport.NumberOfParkingPlaces - numberOfUsedPlaces,
			NumberOfPlaces:          vertiport.NumberOfParkingPlaces,
		}
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}
