package vrp

import (
	"context"
	"github.com/golang/protobuf/ptypes"
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	dsserr "github.com/interuss/dss/pkg/errors"
	dssmodels "github.com/interuss/dss/pkg/models"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/interuss/dss/pkg/vrp/repos"
	"github.com/interuss/stacktrace"
)

//TODO: test this
func (a *Server) GetNumberOfUsedParkingPlaces(ctx context.Context, req *vrppb.GetNumberOfUsedParkingPlacesRequest) (*vrppb.GetNumberOfUsedParkingPlacesResponse, error) {
	id, err := dssmodels.IDFromString(req.GetVertiportid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetVertiportid())
	}

	params := req.GetParams()

	if params.GetTimeStart() == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Start time is missing")
	}

	if params.GetTimeEnd() == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "End time is missing")
	}

	st := params.GetTimeStart().GetValue()
	startTime, err := ptypes.Timestamp(st)
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Error converting start time from proto")
	}

	et := params.GetTimeEnd().GetValue()
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

		constraints, err := r.SearchVertiportConstraints(ctx, &dssmodels.VertiportReservation{
			VertiportID:   id,
			VertiportZone: dssmodels.ParkingStand,
			StartTime:     &startTime,
			EndTime:       &endTime,
		})

		if err != nil {
			return stacktrace.Propagate(err, "Error finding related vertiport constraints")
		}

		operationalIntents, err := r.SearchVertiportOperationalIntents(ctx, &dssmodels.VertiportReservation{
			VertiportID:   id,
			VertiportZone: dssmodels.ParkingStand,
			StartTime:     &startTime,
			EndTime:       &endTime,
		})

		numberOfUsedPlaces, err := vrpmodels.ComputeNumberOfUsedParkingPlaces(constraints, operationalIntents, startTime, endTime)

		if err != nil {
			return stacktrace.Propagate(err, "Error computing the number of used parking places")
		}

		response = &vrppb.GetNumberOfUsedParkingPlacesResponse{
			NumberOfUsedPlaces:      numberOfUsedPlaces,
			NumberOfAvailablePlaces: vertiport.NumberOfParkingPlaces - numberOfUsedPlaces,
			NumberOfPlaces:          vertiport.NumberOfParkingPlaces,
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

//TODO: test this
func (a *Server) GetVertiportFATOAvailableTimes(ctx context.Context, req *vrppb.GetVertiportFATOAvailableTimesRequest) (*vrppb.GetVertiportFATOAvailableTimesResponse, error) {
	id, err := dssmodels.IDFromString(req.GetVertiportid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", req.GetVertiportid())
	}

	params := req.GetParams()

	if params.GetTimeStart() == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Start time is missing")
	}

	if params.GetTimeEnd() == nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "End time is missing")
	}

	st := params.GetTimeStart().GetValue()
	startTime, err := ptypes.Timestamp(st)
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Error converting start time from proto")
	}

	et := params.GetTimeEnd().GetValue()
	endTime, err := ptypes.Timestamp(et)
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Error converting end time from proto")
	}

	var response *vrppb.GetVertiportFATOAvailableTimesResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		response = &vrppb.GetVertiportFATOAvailableTimesResponse{
			TimePeriod: make([]*vrppb.TimePeriod, 0),
		}

		if err != nil {
			return stacktrace.Propagate(err, "Could not find Vertiport")
		}

		constraints, err := r.SearchVertiportConstraints(ctx, &dssmodels.VertiportReservation{
			VertiportID:   id,
			VertiportZone: dssmodels.FATO,
			StartTime:     &startTime,
			EndTime:       &endTime,
		})

		if err != nil {
			return stacktrace.Propagate(err, "Error finding related vertiport constraints")
		}

		operationalIntents, err := r.SearchVertiportOperationalIntents(ctx, &dssmodels.VertiportReservation{
			VertiportID:   id,
			VertiportZone: dssmodels.FATO,
			StartTime:     &startTime,
			EndTime:       &endTime,
		})

		if err != nil {
			return stacktrace.Propagate(err, "Error finding related vertiport constraints")
		}

		timePeriods, err := vrpmodels.ComputeFreeTimePeriods(constraints, operationalIntents, startTime, endTime)
		if err != nil {
			return stacktrace.Propagate(err, "Error computing free time periods")
		}

		for _, period := range timePeriods {
			protoPeriod, err := period.ToProto()
			if err != nil {
				return stacktrace.Propagate(err, "Error converting time period to proto")
			}
			response.TimePeriod = append(response.TimePeriod, protoPeriod)
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

//TODO: test this
func (a *Server) CreateVertiport(ctx context.Context, req *vrppb.CreateVertiportRequest) (*vrppb.PutVertiportResponse, error) {
	return a.PutVertiport(ctx, req.GetVertiportid(), req.GetParams())
}

//TODO: test this
func (a *Server) UpdateVertiport(ctx context.Context, req *vrppb.UpdateVertiportRequest) (*vrppb.PutVertiportResponse, error) {
	return a.PutVertiport(ctx, req.GetVertiportid(), req.GetParams())
}

//TODO: test this
func (a *Server) PutVertiport(ctx context.Context, vertiportid string, params *vrppb.CreateVertiportRequestParams) (*vrppb.PutVertiportResponse, error) {
	id, err := dssmodels.IDFromString(vertiportid)

	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format: `%s`", vertiportid)
	}

	subreq := &vrpmodels.Vertiport{
		ID:                    id,
		NumberOfParkingPlaces: params.NumberOfParkingPlaces,
	}

	var result *vrppb.PutVertiportResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		sub, err := r.UpsertVertiport(ctx, subreq)
		if err != nil {
			return stacktrace.Propagate(err, "Could not upsert Vertiport into repo")
		}
		if sub == nil {
			return stacktrace.NewError("Upsert returned no Vertiport for ID: %s", id)
		}

		result = &vrppb.PutVertiportResponse{
			Vertiport: &vrppb.Vertiport{
				Id:                    vertiportid,
				NumberOfParkingPlaces: params.NumberOfParkingPlaces,
			},
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

//TODO: test this
func (a *Server) DeleteVertiport(ctx context.Context, req *vrppb.DeleteVertiportRequest) (*vrppb.DeleteVertiportResponse, error) {
	// Retrieve VertiportSubscription ID
	id, err := dssmodels.IDFromString(req.GetVertiportid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format")
	}

	var response *vrppb.DeleteVertiportResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Check to make sure it's ok to delete this VertiportSubscription
		old, err := r.GetVertiport(ctx, id)
		switch {
		case err != nil:
			return stacktrace.Propagate(err, "Could not get VertiportSubscription from repo")
		case old == nil: // Return a 404 here.
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "VertiportSubscription %s not found", id.String())
		}

		// TODO: raise an error if there are related Constraints/OperationalIntents/Subscriptions

		// Delete VertiportSubscription in repo
		err = r.DeleteVertiport(ctx, id)
		if err != nil {
			return stacktrace.Propagate(err, "Could not delete VertiportSubscription from repo")
		}

		// Create response for client
		response = &vrppb.DeleteVertiportResponse{
			Vertiport: &vrppb.Vertiport{
				Id:                    req.GetVertiportid(),
				NumberOfParkingPlaces: old.NumberOfParkingPlaces,
			},
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}

//TODO: test this
func (a *Server) GetVertiport(ctx context.Context, req *vrppb.GetVertiportRequest) (*vrppb.GetVertiportResponse, error) {
	// Retrieve VertiportSubscription ID
	id, err := dssmodels.IDFromString(req.GetVertiportid())
	if err != nil {
		return nil, stacktrace.NewErrorWithCode(dsserr.BadRequest, "Invalid ID format")
	}

	var response *vrppb.GetVertiportResponse
	action := func(ctx context.Context, r repos.Repository) (err error) {
		// Check to make sure it's ok to delete this VertiportSubscription
		vrp, err := r.GetVertiport(ctx, id)
		switch {
		case err != nil:
			return stacktrace.Propagate(err, "Could not get Vertiport from repo")
		case vrp == nil: // Return a 404 here.
			return stacktrace.NewErrorWithCode(dsserr.NotFound, "Vertiport %s not found", id.String())
		}

		// Create response for client
		response = &vrppb.GetVertiportResponse{
			Vertiport: &vrppb.Vertiport{
				Id:                    req.GetVertiportid(),
				NumberOfParkingPlaces: vrp.NumberOfParkingPlaces,
			},
		}

		return nil
	}

	err = a.Store.Transact(ctx, action)
	if err != nil {
		return nil, err // No need to Propagate this error as this is not a useful stacktrace line
	}

	return response, nil
}
