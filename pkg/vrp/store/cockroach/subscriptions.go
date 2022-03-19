package cockroach

import (
	"context"
	"fmt"
	"strings"
	"time"

	dssmodels "github.com/interuss/dss/pkg/models"
	dsssql "github.com/interuss/dss/pkg/sql"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/jackc/pgtype"

	"github.com/interuss/stacktrace"
)

var (
	subscriptionFieldsWithIndices   [13]string
	subscriptionFieldsWithPrefix    string
	subscriptionFieldsWithoutPrefix string
)

// TODO Update database schema and fields below.
func init() {
	subscriptionFieldsWithIndices[0] = "id"
	subscriptionFieldsWithIndices[1] = "owner"
	subscriptionFieldsWithIndices[2] = "version"
	subscriptionFieldsWithIndices[3] = "url"
	subscriptionFieldsWithIndices[4] = "notification_index"
	subscriptionFieldsWithIndices[5] = "notify_for_operations"
	subscriptionFieldsWithIndices[6] = "notify_for_constraints"
	subscriptionFieldsWithIndices[7] = "implicit"
	subscriptionFieldsWithIndices[8] = "starts_at"
	subscriptionFieldsWithIndices[9] = "ends_at"
	subscriptionFieldsWithIndices[10] = "vertiport_id"
	subscriptionFieldsWithIndices[11] = "vertiport_zone"
	subscriptionFieldsWithIndices[12] = "updated_at"

	subscriptionFieldsWithoutPrefix = strings.Join(
		subscriptionFieldsWithIndices[:], ",",
	)

	withPrefix := make([]string, 13)
	for idx, field := range subscriptionFieldsWithIndices {
		withPrefix[idx] = "vrp_subscriptions." + field
	}

	subscriptionFieldsWithPrefix = strings.Join(
		withPrefix[:], ",",
	)
}

//func (c *repo) fetchCellsForSubscription(ctx context.Context, q dsssql.Queryable, id dssmodels.ID) (s2.CellUnion, error) {
//	var (
//		cellsQuery = `
//			SELECT
//				unnest(cells) as cell_id
//			FROM
//				vrp_subscriptions
//			WHERE
//				id = $1
//		`
//	)
//
//	uid, err := id.PgUUID()
//	if err != nil {
//		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
//	}
//	rows, err := q.Query(ctx, cellsQuery, uid)
//	if err != nil {
//		return nil, stacktrace.Propagate(err, "Error in query: %s", cellsQuery)
//	}
//	defer rows.Close()
//
//	var (
//		cu   s2.CellUnion
//		cidi int64
//	)
//	for rows.Next() {
//		err := rows.Scan(&cidi)
//		if err != nil {
//			return nil, stacktrace.Propagate(err, "Error scanning Subscription cell row")
//		}
//		cu = append(cu, s2.CellID(cidi))
//	}
//	if err := rows.Err(); err != nil {
//		return nil, stacktrace.Propagate(err, "Error in rows query result")
//	}
//	return cu, nil
//}

func (c *repo) fetchSubscriptions(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) ([]*vrpmodels.VertiportSubscription, error) {
	rows, err := q.Query(ctx, query, args...)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error in query: %s", query)
	}
	defer rows.Close()

	var payload []*vrpmodels.VertiportSubscription
	for rows.Next() {
		var (
			s         = new(vrpmodels.VertiportSubscription)
			updatedAt time.Time
			version   int
		)
		err = rows.Scan(
			&s.ID,
			&s.Manager,
			&version,
			&s.USSBaseURL,
			&s.NotificationIndex,
			&s.NotifyForOperationalIntents,
			&s.NotifyForConstraints,
			&s.ImplicitSubscription,
			&s.StartTime,
			&s.EndTime,
			&s.VertiportID,
			&s.VertiportZone,
			&updatedAt,
		)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error scanning Subscription row")
		}
		s.Version = vrpmodels.NewOVNFromTime(updatedAt, s.ID.String())
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error generating Subscription version")
		}
		payload = append(payload, s)
	}
	if err = rows.Err(); err != nil {
		return nil, stacktrace.Propagate(err, "Error in rows query result")
	}

	return payload, nil
}

func (c *repo) fetchSubscription(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) (*vrpmodels.VertiportSubscription, error) {
	subs, err := c.fetchSubscriptions(ctx, q, query, args...)
	if err != nil {
		return nil, err
	}
	if len(subs) > 1 {
		return nil, stacktrace.NewError("Query returned %d subscriptions when only 0 or 1 was expected", len(subs))
	}
	if len(subs) == 0 {
		return nil, nil
	}
	return subs[0], nil
}

func (c *repo) fetchSubscriptionByID(ctx context.Context, q dsssql.Queryable, id dssmodels.ID) (*vrpmodels.VertiportSubscription, error) {
	var (
		query = fmt.Sprintf(`
			SELECT
				%s
			FROM
				vrp_subscriptions
			WHERE
				id = $1`, subscriptionFieldsWithPrefix)
	)
	uid, err := id.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	result, err := c.fetchSubscription(ctx, q, query, uid)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Subscription")
	}
	if result == nil {
		return nil, nil
	}
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching cells for Subscription")
	}
	return result, nil
}

func (c *repo) pushSubscription(ctx context.Context, q dsssql.Queryable, s *vrpmodels.VertiportSubscription) (*vrpmodels.VertiportSubscription, error) {
	var (
		upsertQuery = fmt.Sprintf(`
		WITH v AS (
			SELECT
				version
			FROM
				vrp_subscriptions
			WHERE
				id = $1
		)
		UPSERT INTO
		  vrp_subscriptions
		  (%s)
		VALUES
			($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, transaction_timestamp())
		RETURNING
			%s`, subscriptionFieldsWithoutPrefix, subscriptionFieldsWithPrefix)
	)

	id, err := s.ID.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	s, err = c.fetchSubscription(ctx, q, upsertQuery,
		id,
		s.Manager,
		0,
		s.USSBaseURL,
		s.NotificationIndex,
		s.NotifyForOperationalIntents,
		s.NotifyForConstraints,
		s.ImplicitSubscription,
		s.StartTime,
		s.EndTime,
		s.VertiportID,
		s.VertiportZone,
	)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Subscription from upsert query")
	}
	if s == nil {
		return nil, stacktrace.NewError("Upsert query did not return a Subscription")
	}

	return s, nil
}

// GetSubscription returns the subscription identified by "id".
func (c *repo) GetVertiportSubscription(ctx context.Context, id dssmodels.ID) (*vrpmodels.VertiportSubscription, error) {
	sub, err := c.fetchSubscriptionByID(ctx, c.q, id)
	if err != nil {
		return nil, err // No need to Propagate this error as this stack layer does not add useful information
	} else if sub == nil {
		return nil, nil
	}
	return sub, nil
}

// Implements repos.Subscription.UpsertSubscription
func (c *repo) UpsertVertiportSubscription(ctx context.Context, s *vrpmodels.VertiportSubscription) (*vrpmodels.VertiportSubscription, error) {
	newSubscription, err := c.pushSubscription(ctx, c.q, s)
	if err != nil {
		return nil, err // No need to Propagate this error as this stack layer does not add useful information
	}

	return newSubscription, nil
}

// DeleteSubscription deletes the subscription identified by "id" and
// returns the deleted subscription.
func (c *repo) DeleteVertiportSubscription(ctx context.Context, id dssmodels.ID) error {
	const (
		query = `
		DELETE FROM
			vrp_subscriptions
		WHERE
			id = $1`
	)

	uid, err := id.PgUUID()
	if err != nil {
		return stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	res, err := c.q.Exec(ctx, query, uid)
	if err != nil {
		return stacktrace.Propagate(err, "Error in query: %s", query)
	}

	if res.RowsAffected() == 0 {
		return stacktrace.NewError("Attempted to delete non-existent Subscription")
	}

	return nil
}

// Implements SubscriptionStore.SearchSubscriptions
func (c *repo) SearchVertiportSubscriptions(ctx context.Context, v4d *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportSubscription, error) {
	var (
		query = fmt.Sprintf(`
			SELECT
				%s
			FROM
				vrp_subscriptions
				WHERE
					vertiport_id == $1 && vertiport_zone == $2
				AND
					COALESCE(starts_at <= $4, true)
				AND
					COALESCE(ends_at >= $3, true)
				LIMIT $5`, subscriptionFieldsWithPrefix)
	)

	subscriptions, err := c.fetchSubscriptions(
		ctx, c.q, query, v4d.VertiportID, v4d.VertiportZone, v4d.StartTime, v4d.EndTime, dssmodels.MaxResultLimit)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Unable to fetch Subscriptions")
	}

	return subscriptions, nil
}

// Implements scd.repos.Subscription.IncrementNotificationIndices
func (c *repo) IncrementNotificationIndices(ctx context.Context, subscriptionIds []dssmodels.ID) ([]int, error) {
	var updateQuery = `
			UPDATE vrp_subscriptions
			SET notification_index = notification_index + 1
			WHERE id = ANY($1)
			RETURNING notification_index`

	ids := make([]string, len(subscriptionIds))
	for i, id := range subscriptionIds {
		ids[i] = id.String()
	}

	var pgIds pgtype.UUIDArray
	err := pgIds.Set(ids)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert array to jackc/pgtype")
	}
	rows, err := c.q.Query(ctx, updateQuery, pgIds)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error in query: %s", updateQuery)
	}
	defer rows.Close()

	var indices []int
	for rows.Next() {
		var notificationIndex int
		err := rows.Scan(&notificationIndex)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error scanning notification index row")
		}
		indices = append(indices, notificationIndex)
	}
	if err := rows.Err(); err != nil {
		return nil, stacktrace.Propagate(err, "Error in rows query result")
	}

	if len(indices) != len(subscriptionIds) {
		return nil, stacktrace.NewError(
			"Expected %d notification_index results when incrementing but got %d instead",
			len(subscriptionIds), len(indices))
	}

	return indices, nil
}
