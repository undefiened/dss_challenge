package models

import (
	dssmodels "github.com/interuss/dss/pkg/models"
)

type Vertiport struct {
	ID                    dssmodels.ID
	NumberOfParkingPlaces int32
}
