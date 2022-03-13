package models

import "time"

type VertiportPosition = int

const (
	FATO         VertiportPosition = 0
	ParkingStand                   = 1
)

type Vertiport struct {
	Position        *LatLngPoint
	ID              int
	ParkingCapacity int
}

type VertiportReservation struct {
	Vertiport         *Vertiport
	VertiportPosition *VertiportPosition
	StartTime         *time.Time
	EndTime           *time.Time
}
