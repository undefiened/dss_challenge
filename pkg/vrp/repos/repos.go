package repos

import (
	"context"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"

	dssmodels "github.com/interuss/dss/pkg/models"
)

// Subscriptions enables operations on a list of Subscriptions.
type VertiportSubscriptions []*vrpmodels.VertiportSubscription

// VertiportOperationalIntent abstracts operational intent-specific interactions with the backing repository.
type VertiportOperationalIntent interface {
	// GetVertiportOperationalIntent returns the operation identified by "id".
	GetVertiportOperationalIntent(ctx context.Context, id dssmodels.ID) (*vrpmodels.VertiportOperationalIntent, error)

	// DeleteVertiportOperationalIntent deletes the operation identified by "id".
	DeleteVertiportOperationalIntent(ctx context.Context, id dssmodels.ID) error

	// UpsertVertiportOperationalIntent inserts or updates an operation into the store.
	UpsertVertiportOperationalIntent(ctx context.Context, operation *vrpmodels.VertiportOperationalIntent) (*vrpmodels.VertiportOperationalIntent, error)

	// SearchVertiportOperationalIntents returns all operations taking place in particular vertiport at time and zone
	SearchVertiportOperationalIntents(ctx context.Context, vertiportReservation *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportOperationalIntent, error)

	// GetDependentVertiportOperationalIntents returns IDs of all operations dependent on
	// subscription identified by "subscriptionID".
	GetDependentVertiportOperationalIntents(ctx context.Context, subscriptionID dssmodels.ID) ([]dssmodels.ID, error)
}

// VertiportSubscription abstracts subscription-specific interactions with the backing repository.
type VertiportSubscription interface {
	// SearchVertiportSubscriptions returns all Subscriptions in vertiport.
	SearchVertiportSubscriptions(ctx context.Context, vertiportReservation *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportSubscription, error)

	// GetVertiportSubscription returns the Subscription referenced by id, or nil and no
	// error if the Subscription doesn't exist
	GetVertiportSubscription(ctx context.Context, id dssmodels.ID) (*vrpmodels.VertiportSubscription, error)

	// UpsertVertiportSubscription upserts sub into the store and returns the result
	// subscription.
	UpsertVertiportSubscription(ctx context.Context, sub *vrpmodels.VertiportSubscription) (*vrpmodels.VertiportSubscription, error)

	// DeleteVertiportSubscription deletes a Subscription from the store and returns the
	// deleted subscription.  Returns an error if the Subscription does not
	// exist.
	DeleteVertiportSubscription(ctx context.Context, id dssmodels.ID) error

	// IncrementNotificationIndices increments the notification index of each
	// specified Subscription and returns the resulting corresponding
	// notification indices.
	IncrementNotificationIndices(ctx context.Context, subscriptionIds []dssmodels.ID) ([]int, error)
}

//// repos.Constraint abstracts constraint-specific interactions with the backing store.
type VertiportConstraint interface {
	// SearchConstraints returns all Constraints in "v4d".
	SearchVertiportConstraints(ctx context.Context, vertiportReservation *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportConstraint, error)

	// GetConstraint returns the Constraint referenced by id, or
	// (nil, sql.ErrNoRows) if the Constraint doesn't exist
	GetVertiportConstraint(ctx context.Context, id dssmodels.ID) (*vrpmodels.VertiportConstraint, error)

	// UpsertConstraint upserts "constraint" into the store.
	UpsertVertiportConstraint(ctx context.Context, constraint *vrpmodels.VertiportConstraint) (*vrpmodels.VertiportConstraint, error)

	// DeleteConstraint deletes a Constraint from the store and returns the
	// deleted subscription.  Returns nil and an error if the Constraint does
	// not exist.
	DeleteVertiportConstraint(ctx context.Context, id dssmodels.ID) error
}

// Repository aggregates all VRP-specific repo interfaces.
type Repository interface {
	VertiportOperationalIntent
	VertiportSubscription
	VertiportConstraint
}

// IncrementNotificationIndices is a utility function that extracts the IDs from
// a list of Subscriptions before calling the underlying repo function, and then
// updates the Subscription objects with the new notification indices.
func (subs VertiportSubscriptions) IncrementNotificationIndices(ctx context.Context, r Repository) error {
	subIds := make([]dssmodels.ID, len(subs))
	for i, sub := range subs {
		subIds[i] = sub.ID
	}
	newIndices, err := r.IncrementNotificationIndices(ctx, subIds)
	if err != nil {
		return err
	}
	for i, newIndex := range newIndices {
		subs[i].NotificationIndex = newIndex
	}
	return nil
}
