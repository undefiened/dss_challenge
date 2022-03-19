package vrp

import (
	"github.com/interuss/dss/pkg/api/v1/vrppb"
	"github.com/interuss/dss/pkg/auth"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	vrpstore "github.com/interuss/dss/pkg/vrp/store"
	"time"
)

const (
	strategicCoordinationScope   = "utm.strategic_coordination"
	constraintManagementScope    = "utm.constraint_management"
	constraintProcessingScope    = "utm.constraint_processing"
	conformanceMonitoringSAScope = "utm.conformance_monitoring_sa"
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
		"/vrppb.UTMAPIVertiportsService/CreateVertiportConstraintReference":        auth.RequireAnyScope(constraintManagementScope),
		"/vrppb.UTMAPIVertiportsService/CreateVertiportOperationalIntentReference": auth.RequireAnyScope(strategicCoordinationScope, conformanceMonitoringSAScope),
		"/vrppb.UTMAPIVertiportsService/CreateVertiportSubscription":               auth.RequireAnyScope(strategicCoordinationScope, constraintProcessingScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiportConstraintReference":        auth.RequireAnyScope(constraintManagementScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiportOperationalIntentReference": auth.RequireAnyScope(strategicCoordinationScope, conformanceMonitoringSAScope),
		"/vrppb.UTMAPIVertiportsService/DeleteVertiportSubscription":               auth.RequireAnyScope(strategicCoordinationScope, constraintProcessingScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportConstraintReference":           auth.RequireAnyScope(constraintManagementScope, constraintProcessingScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportOperationalIntentReference":    auth.RequireAnyScope(strategicCoordinationScope, conformanceMonitoringSAScope),
		"/vrppb.UTMAPIVertiportsService/GetVertiportSubscription":                  auth.RequireAnyScope(strategicCoordinationScope, constraintProcessingScope),
		"/vrppb.UTMAPIVertiportsService/QueryVertiportConstraintReferences":        auth.RequireAnyScope(constraintProcessingScope, constraintManagementScope),
		"/vrppb.UTMAPIVertiportsService/QueryVertiportOperationalIntentReferences": auth.RequireAnyScope(strategicCoordinationScope, conformanceMonitoringSAScope),
		"/vrppb.UTMAPIVertiportsService/QueryVertiportSubscriptions":               auth.RequireAnyScope(strategicCoordinationScope, constraintProcessingScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiportConstraintReference":        auth.RequireAnyScope(constraintManagementScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiportOperationalIntentReference": auth.RequireAnyScope(strategicCoordinationScope, conformanceMonitoringSAScope),
		"/vrppb.UTMAPIVertiportsService/UpdateVertiportSubscription":               auth.RequireAnyScope(strategicCoordinationScope, constraintProcessingScope),
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
