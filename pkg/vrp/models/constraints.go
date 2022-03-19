package models

import (
	"github.com/golang/protobuf/ptypes"
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	dsserr "github.com/interuss/dss/pkg/errors"
	dssmodels "github.com/interuss/dss/pkg/models"
	scdmodels "github.com/interuss/dss/pkg/scd/models"
	"github.com/interuss/stacktrace"
	"time"
)

type VertiportConstraint struct {
	ID              dssmodels.ID
	Manager         dssmodels.Manager
	UssAvailability scdmodels.UssAvailabilityState
	Version         VersionNumber
	OVN             OVN
	StartTime       *time.Time
	EndTime         *time.Time
	USSBaseURL      string
	VertiportID     dssmodels.ID
	VertiportZone   int32
}

// ToProto converts the Constraint to its proto API format
func (c *VertiportConstraint) ToProto() (*vrppb.VertiportConstraintReference, error) {
	result := &vrppb.VertiportConstraintReference{
		Id:              c.ID.String(),
		Ovn:             c.OVN.String(),
		Manager:         c.Manager.String(),
		Version:         int32(c.Version),
		UssBaseUrl:      c.USSBaseURL,
		UssAvailability: scdmodels.UssAvailabilityStateUnknown.String(),
	}

	if c.StartTime != nil {
		ts, err := ptypes.TimestampProto(*c.StartTime)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error converting start time to proto")
		}
		result.TimeStart = &vrppb.Time{
			Value:  ts,
			Format: dssmodels.TimeFormatRFC3339,
		}
	}

	if c.EndTime != nil {
		ts, err := ptypes.TimestampProto(*c.EndTime)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error converting end time to proto")
		}
		result.TimeEnd = &vrppb.Time{
			Value:  ts,
			Format: dssmodels.TimeFormatRFC3339,
		}
	}

	return result, nil
}

// ValidateTimeRange validates the time range of c.
func (c *VertiportConstraint) ValidateTimeRange() error {
	if c.StartTime == nil {
		return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Constraint must have an time_start")
	}

	// EndTime cannot be omitted for new Constraints.
	if c.EndTime == nil {
		return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Constraint must have an time_end")
	}

	// EndTime cannot be before StartTime.
	if c.EndTime.Sub(*c.StartTime) < 0 {
		return stacktrace.NewErrorWithCode(dsserr.BadRequest, "Constraint time_end must be after time_start")
	}

	return nil
}
