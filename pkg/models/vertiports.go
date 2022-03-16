package models

import (
	"github.com/golang/protobuf/ptypes"
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	"github.com/interuss/stacktrace"
	"time"
)

const (
	FATO         int32 = 0
	ParkingStand       = 1
)

type Vertiport struct {
	Position        *LatLngPoint
	ID              int
	ParkingCapacity int
}

type VertiportReservation struct {
	VertiportID   ID
	VertiportZone int32
	StartTime     *time.Time
	EndTime       *time.Time
}

func VertiportReservationFromVRPProto(vr *vrppb.VertiportReservation) (*VertiportReservation, error) {
	result := &VertiportReservation{
		VertiportZone: vr.GetReservedZone(),
		VertiportID:   ID(vr.GetVertiportid()),
	}

	if startTime := vr.GetTimeStart(); startTime != nil {
		st := startTime.GetValue()
		ts, err := ptypes.Timestamp(st)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error converting start time from proto")
		}
		result.StartTime = &ts
	}

	if endTime := vr.GetTimeEnd(); endTime != nil {
		et := endTime.GetValue()
		ts, err := ptypes.Timestamp(et)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error converting end time from proto")
		}
		result.EndTime = &ts
	}

	return result, nil
}
