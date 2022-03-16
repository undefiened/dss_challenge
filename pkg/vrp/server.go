package vrp

import (
	"github.com/interuss/dss/pkg/auth"
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
