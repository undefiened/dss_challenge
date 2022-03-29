package models

import (
	"crypto/sha256"
	"encoding/base64"
	"github.com/golang/protobuf/ptypes"
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	dssmodels "github.com/interuss/dss/pkg/models"
	"net/url"
	"strings"
	"time"

	"github.com/interuss/stacktrace"
)

const (
	// Value for OVN that should be returned for entities not owned by the client
	NoOvnPhrase = "Available from USS"
)

type (
	// OVN models an opaque version number.
	OVN string

	// Version models the version of an entity.
	// Primarily used as a fencing token in data mutations.
	VersionNumber int32
)

type TimePeriod struct {
	From *time.Time
	To   *time.Time
}

func (tp *TimePeriod) ToProto() (*vrppb.TimePeriod, error) {
	result := &vrppb.TimePeriod{}

	if tp.From != nil {
		ts, err := ptypes.TimestampProto(*tp.From)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error converting start time to proto")
		}
		result.From = &vrppb.Time{
			Value:  ts,
			Format: dssmodels.TimeFormatRFC3339,
		}
	}

	if tp.To != nil {
		ts, err := ptypes.TimestampProto(*tp.To)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error converting start time to proto")
		}
		result.To = &vrppb.Time{
			Value:  ts,
			Format: dssmodels.TimeFormatRFC3339,
		}
	}

	return result, nil
}

func (tp *TimePeriod) IntersectsWith(anotherPeriod *TimePeriod) bool {
	if tp.From.After(*anotherPeriod.To) || tp.From.Equal(*anotherPeriod.To) || tp.To.Before(*anotherPeriod.From) || tp.To.Equal(*anotherPeriod.From) {
		return false
	}

	return true
}

func (tp *TimePeriod) Cut(periodToCut *TimePeriod) ([]*TimePeriod, error) {
	result := make([]*TimePeriod, 0)

	// periodToCut completely covers tp, the result is nothing
	if (tp.From.After(*periodToCut.From) && tp.To.Before(*periodToCut.To)) || (tp.From.Equal(*periodToCut.From) && tp.To.Equal(*periodToCut.To)) {
		return result, nil
	}

	// periodToCut covers the beginning of tp but not the end, the result is one time period
	if (tp.From.After(*periodToCut.From) || tp.From.Equal(*periodToCut.From)) && tp.To.After(*periodToCut.To) {
		result = append(result, &TimePeriod{
			From: periodToCut.To,
			To:   tp.To,
		})
		return result, nil
	}

	// periodToCut covers the end of tp but not the beginning
	if (tp.To.Before(*periodToCut.To) || tp.To.Equal(*periodToCut.To)) && tp.From.Before(*periodToCut.From) {
		result = append(result, &TimePeriod{
			From: tp.From,
			To:   periodToCut.From,
		})
		return result, nil
	}

	// periodToCut is inside of tp
	if tp.To.After(*periodToCut.To) && tp.From.Before(*periodToCut.From) {
		result = append(result, &TimePeriod{
			From: tp.From,
			To:   periodToCut.From,
		})
		result = append(result, &TimePeriod{
			From: periodToCut.To,
			To:   tp.From,
		})
		return result, nil
	}

	return nil, stacktrace.NewError("Time period to cut is wrong")
}

func ComputeFreeTimePeriods(constraints []*VertiportConstraint, operationalIntents []*VertiportOperationalIntent, timeStart time.Time, timeEnd time.Time) ([]*TimePeriod, error) {
	resultingTimePeriods := make([]*TimePeriod, 1)
	resultingTimePeriods = append(resultingTimePeriods, &TimePeriod{
		From: &timeStart,
		To:   &timeEnd,
	})
	busyTimePeriods := make([]*TimePeriod, len(constraints)+len(operationalIntents))

	for _, constraint := range constraints {
		busyTimePeriods = append(busyTimePeriods, &TimePeriod{
			From: constraint.StartTime,
			To:   constraint.EndTime,
		})
	}

	for _, constraint := range operationalIntents {
		busyTimePeriods = append(busyTimePeriods, &TimePeriod{
			From: constraint.StartTime,
			To:   constraint.EndTime,
		})
	}

	for _, timePeriodToCut := range busyTimePeriods {
		newResultingTimePeriods := make([]*TimePeriod, 0)

		for _, period := range resultingTimePeriods {
			if period.IntersectsWith(timePeriodToCut) {
				res, err := period.Cut(timePeriodToCut)

				if err != nil {
					return nil, err
				}

				for _, cuttedRange := range res {
					newResultingTimePeriods = append(newResultingTimePeriods, cuttedRange)
				}
			} else {
				newResultingTimePeriods = append(newResultingTimePeriods, period)
			}
		}

		resultingTimePeriods = newResultingTimePeriods
	}

	return resultingTimePeriods, nil
}

// NewOVNFromTime encodes t as an OVN.
func NewOVNFromTime(t time.Time, salt string) OVN {
	sum := sha256.Sum256([]byte(salt + t.Format(time.RFC3339)))
	ovn := base64.StdEncoding.EncodeToString(
		sum[:],
	)
	ovn = strings.Replace(ovn, "+", "-", -1)
	ovn = strings.Replace(ovn, "/", ".", -1)
	ovn = strings.Replace(ovn, "=", "_", -1)
	return OVN(ovn)
}

// Empty returns true if ovn indicates an empty opaque version number.
func (ovn OVN) Empty() bool {
	return len(ovn) == 0
}

// Valid returns true if ovn is valid.
func (ovn OVN) Valid() bool {
	return len(ovn) >= 16 && len(ovn) <= 128
}

func (ovn OVN) String() string {
	return string(ovn)
}

// Empty returns true if the value of v indicates an empty version.
func (v VersionNumber) Empty() bool {
	return v <= 0
}

// Matches returns true if v matches w.
func (v VersionNumber) Matches(w VersionNumber) bool {
	return v == w
}

// ValidateUSSBaseURL ensures https
func ValidateUSSBaseURL(s string) error {
	u, err := url.Parse(s)
	if err != nil {
		return stacktrace.Propagate(err, "Error parsing URL")
	}

	switch u.Scheme {
	case "https":
		// All good, proceed normally.
	case "http":
		return stacktrace.NewError("uss_base_url must use TLS")
	default:
		return stacktrace.NewError("uss_base_url must support https scheme")
	}

	return nil
}
