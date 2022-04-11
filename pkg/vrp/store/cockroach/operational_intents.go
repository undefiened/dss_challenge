package cockroach

import (
	"context"
	"fmt"
	"strings"
	"time"

	dssmodels "github.com/interuss/dss/pkg/models"
	dsssql "github.com/interuss/dss/pkg/sql"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/interuss/stacktrace"
)

var (
	operationFieldsWithIndices   [11]string
	operationFieldsWithPrefix    string
	operationFieldsWithoutPrefix string
)

// TODO Update database schema and fields below.
func init() {
	operationFieldsWithIndices[0] = "id"
	operationFieldsWithIndices[1] = "owner"
	operationFieldsWithIndices[2] = "version"
	operationFieldsWithIndices[3] = "url"
	operationFieldsWithIndices[4] = "vertiport_id"
	operationFieldsWithIndices[5] = "vertiport_zone"
	operationFieldsWithIndices[6] = "starts_at"
	operationFieldsWithIndices[7] = "ends_at"
	operationFieldsWithIndices[8] = "subscription_id"
	operationFieldsWithIndices[9] = "updated_at"
	operationFieldsWithIndices[10] = "state"

	operationFieldsWithoutPrefix = strings.Join(
		operationFieldsWithIndices[:], ",",
	)

	withPrefix := make([]string, len(operationFieldsWithIndices))
	for idx, field := range operationFieldsWithIndices {
		withPrefix[idx] = "vrp_operations." + field
	}

	operationFieldsWithPrefix = strings.Join(
		withPrefix[:], ",",
	)
}

func (s *repo) fetchOperationalIntents(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) ([]*vrpmodels.VertiportOperationalIntent, error) {
	rows, err := q.Query(ctx, query, args...)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error in query: %s", query)
	}
	defer rows.Close()

	var payload []*vrpmodels.VertiportOperationalIntent
	for rows.Next() {
		var (
			o         = &vrpmodels.VertiportOperationalIntent{}
			updatedAt time.Time
		)
		err := rows.Scan(
			&o.ID,
			&o.Manager,
			&o.Version,
			&o.USSBaseURL,
			&o.VertiportID,
			&o.VertiportZone,
			&o.StartTime,
			&o.EndTime,
			&o.SubscriptionID,
			&updatedAt,
			&o.State,
		)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error scanning Operation row")
		}
		o.OVN = vrpmodels.NewOVNFromTime(updatedAt, o.ID.String())
		payload = append(payload, o)
	}
	if err := rows.Err(); err != nil {
		return nil, stacktrace.Propagate(err, "Error in rows query result")
	}

	//for _, op := range payload {
	//	if err := s.populateOperationalIntentCells(ctx, q, op); err != nil {
	//		return nil, stacktrace.Propagate(err, "Error populating cells for Operation %s", op.ID)
	//	}
	//}

	return payload, nil
}

func (s *repo) fetchOperationalIntent(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) (*vrpmodels.VertiportOperationalIntent, error) {
	operations, err := s.fetchOperationalIntents(ctx, q, query, args...)
	if err != nil {
		return nil, err
	}
	if len(operations) > 1 {
		return nil, stacktrace.NewError("Query returned %d Operations when only 0 or 1 was expected", len(operations))
	}
	if len(operations) == 0 {
		return nil, nil
	}
	return operations[0], nil
}

func (s *repo) fetchOperationByID(ctx context.Context, q dsssql.Queryable, id dssmodels.ID) (*vrpmodels.VertiportOperationalIntent, error) {
	query := fmt.Sprintf(`
		SELECT %s FROM
			vrp_operations
		WHERE
			id = $1`, operationFieldsWithoutPrefix)
	uid, err := id.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	return s.fetchOperationalIntent(ctx, q, query, uid)
}

//func (s *repo) populateOperationalIntentCells(ctx context.Context, q dsssql.Queryable, o *vrpmodels.VertiportOperationalIntent) error {
//	const query = `
//	SELECT
//		unnest(cells) as cell_id
//	FROM
//		vrp_operations
//	WHERE id = $1`
//
//	uid, err := o.ID.PgUUID()
//	if err != nil {
//		return stacktrace.Propagate(err, "Failed to convert id to PgUUID")
//	}
//	rows, err := q.Query(ctx, query, uid)
//	if err != nil {
//		return stacktrace.Propagate(err, "Error in query: %s", query)
//	}
//	defer rows.Close()
//
//	var cell int64
//	o.Cells = s2.CellUnion{}
//
//	for rows.Next() {
//		if err := rows.Scan(&cell); err != nil {
//			return stacktrace.Propagate(err, "Error scanning cell ID row")
//		}
//		o.Cells = append(o.Cells, s2.CellID(uint64(cell)))
//	}
//	if err := rows.Err(); err != nil {
//		return stacktrace.Propagate(err, "Error in rows query result")
//	}
//
//	return nil
//}

// GetOperation implements repos.Operation.GetOperation.
func (s *repo) GetVertiportOperationalIntent(ctx context.Context, id dssmodels.ID) (*vrpmodels.VertiportOperationalIntent, error) {
	return s.fetchOperationByID(ctx, s.q, id)
}

// DeleteOperation implements repos.Operation.DeleteOperation.
func (s *repo) DeleteVertiportOperationalIntent(ctx context.Context, id dssmodels.ID) error {
	var (
		deleteOperationQuery = `
			DELETE FROM
				vrp_operations
			WHERE
				id = $1
		`
	)

	uid, err := id.PgUUID()
	if err != nil {
		return stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	res, err := s.q.Exec(ctx, deleteOperationQuery, uid)
	if err != nil {
		return stacktrace.Propagate(err, "Error in query: %s", deleteOperationQuery)
	}

	if res.RowsAffected() == 0 {
		return stacktrace.NewError("Could not delete Operation that does not exist")
	}

	return nil
}

// UpsertOperation implements repos.Operation.UpsertOperation.
func (s *repo) UpsertVertiportOperationalIntent(ctx context.Context, operation *vrpmodels.VertiportOperationalIntent) (*vrpmodels.VertiportOperationalIntent, error) {
	var (
		upsertOperationsQuery = fmt.Sprintf(`
			UPSERT INTO
				vrp_operations
				(%s)
			VALUES
				($1, $2, $3, $4, $5, $6, $7, $8, $9, transaction_timestamp(), $10)
			RETURNING
				%s`, operationFieldsWithoutPrefix, operationFieldsWithPrefix)
	)

	opid, err := operation.ID.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	subid, err := operation.SubscriptionID.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	operation, err = s.fetchOperationalIntent(ctx, s.q, upsertOperationsQuery,
		opid,
		operation.Manager,
		operation.Version,
		operation.USSBaseURL,
		operation.VertiportID,
		operation.VertiportZone,
		operation.StartTime,
		operation.EndTime,
		subid,
		operation.State,
	)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Operation")
	}

	return operation, nil
}

func (s *repo) searchOperationalIntents(ctx context.Context, q dsssql.Queryable, reservation *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportOperationalIntent, error) {
	var (
		operationsIntersectingVertiportQuery = fmt.Sprintf(`
			SELECT
				%s
			FROM
				vrp_operations
			WHERE
				vertiport_id = $1 AND vertiport_zone = $2
			AND
				COALESCE(vrp_operations.ends_at >= $3, true)
			AND
				COALESCE(vrp_operations.starts_at <= $4, true)
			LIMIT $5`, operationFieldsWithPrefix)
	)

	result, err := s.fetchOperationalIntents(
		ctx, q, operationsIntersectingVertiportQuery,
		reservation.VertiportID,
		reservation.VertiportZone,
		reservation.StartTime,
		reservation.EndTime,
		dssmodels.MaxResultLimit,
	)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Operations")
	}

	return result, nil
}

// SearchOperations implements repos.Operation.SearchOperations.
func (s *repo) SearchVertiportOperationalIntents(ctx context.Context, reservation *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportOperationalIntent, error) {
	return s.searchOperationalIntents(ctx, s.q, reservation)
}

// GetDependentOperations implements repos.Operation.GetDependentOperations.
func (s *repo) GetDependentVertiportOperationalIntents(ctx context.Context, subscriptionID dssmodels.ID) ([]dssmodels.ID, error) {
	var dependentOperationsQuery = `
      SELECT
        id
      FROM
        vrp_operations
      WHERE
        subscription_id = $1`

	subid, err := subscriptionID.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	rows, err := s.q.Query(ctx, dependentOperationsQuery, subid)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error in query: %s", dependentOperationsQuery)
	}
	defer rows.Close()
	var opID dssmodels.ID
	var dependentOps []dssmodels.ID
	for rows.Next() {
		err = rows.Scan(&opID)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error scanning dependent Operation ID")
		}
		dependentOps = append(dependentOps, opID)
	}

	return dependentOps, nil
}
