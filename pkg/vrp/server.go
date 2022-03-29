package vrp

import (
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	"github.com/interuss/dss/pkg/auth"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	vrpstore "github.com/interuss/dss/pkg/vrp/store"
	"time"
)

const (
	vertiportScope = "utm.vertiport_management"
)

// Server implements vrppb.DiscoveryAndSynchronizationService.
type Server struct {
	Timeout    time.Duration
	EnableHTTP bool
	Store      vrpstore.Store
}

// AuthScopes returns a map of endpoint to required Oauth scope.
func (a *Server) AuthScopes() map[auth.Operation]auth.KeyClaimedScopesValidator {
	return map[auth.Operation]auth.KeyClaimedScopesValidator{
		"/vrppb.UTMAPIVertiportsService/CreateVertiportConstraintReference":        auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/CreateVertiportOperationalIntentReference": auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/CreateVertiportSubscription":               auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/CreateVertiport":                           auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiportConstraintReference":        auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiportOperationalIntentReference": auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiportSubscription":               auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiport":                           auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportConstraintReference":           auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportOperationalIntentReference":    auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportSubscription":                  auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/QueryVertiportConstraintReferences":        auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/QueryVertiportOperationalIntentReferences": auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/QueryVertiportSubscriptions":               auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiportConstraintReference":        auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiportOperationalIntentReference": auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiportSubscription":               auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiport":                           auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportFATOAvailableTimes":            auth.RequireAnyScope(vertiportScope),
		"/vrppb.UTMAPIVertiportsService/GetNumberOfUsedParkingPlaces":              auth.RequireAnyScope(vertiportScope),
	}
}

func makeSubscribersToNotify(subscriptions []*vrpmodels.VertiportSubscription) []*vrppb.VertiportSubscriberToNotify {
	result := []*vrppb.VertiportSubscriberToNotify{}

	subscriptionsByURL := map[string][]*vrppb.VertiportSubscriptionState{}
	for _, sub := range subscriptions {
		subState := &vrppb.VertiportSubscriptionState{
			SubscriptionId:    sub.ID.String(),
			NotificationIndex: int32(sub.NotificationIndex),
		}
		subscriptionsByURL[sub.USSBaseURL] = append(subscriptionsByURL[sub.USSBaseURL], subState)
	}
	for url, states := range subscriptionsByURL {
		result = append(result, &vrppb.VertiportSubscriberToNotify{
			UssBaseUrl:    url,
			Subscriptions: states,
		})
	}

	return result
}
