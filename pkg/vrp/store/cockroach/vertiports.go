package cockroach

import (
	"context"
	"fmt"
	dssmodels "github.com/interuss/dss/pkg/models"
	dsssql "github.com/interuss/dss/pkg/sql"
	vrpmodels "github.com/interuss/dss/pkg/vrp/models"
	"github.com/interuss/stacktrace"
	"strings"
)

var (
	vertiportFieldsWithIndices   [2]string
	vertiportFieldsWithPrefix    string
	vertiportFieldsWithoutPrefix string
)

// TODO Update database schema and fields below.
func init() {
	vertiportFieldsWithIndices[0] = "id"
	vertiportFieldsWithIndices[1] = "number_of_parking_places"

	vertiportFieldsWithoutPrefix = strings.Join(
		vertiportFieldsWithIndices[:], ",",
	)

	withPrefix := make([]string, len(vertiportFieldsWithIndices))
	for idx, field := range vertiportFieldsWithIndices {
		withPrefix[idx] = "vrp_vertiports." + field
	}

	vertiportFieldsWithPrefix = strings.Join(
		withPrefix[:], ",",
	)
}

func (s *repo) fetchVertiports(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) ([]*vrpmodels.Vertiport, error) {
	rows, err := q.Query(ctx, query, args...)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error in query: %s", query)
	}
	defer rows.Close()

	var payload []*vrpmodels.Vertiport
	for rows.Next() {
		var (
			o = &vrpmodels.Vertiport{}
		)
		err := rows.Scan(
			&o.ID,
			&o.NumberOfParkingPlaces,
		)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error scanning Operation row")
		}
		payload = append(payload, o)
	}
	if err := rows.Err(); err != nil {
		return nil, stacktrace.Propagate(err, "Error in rows query result")
	}

	return payload, nil
}

func (s *repo) fetchVertiport(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) (*vrpmodels.Vertiport, error) {
	vertiports, err := s.fetchVertiports(ctx, q, query, args...)
	if err != nil {
		return nil, err
	}
	if len(vertiports) > 1 {
		return nil, stacktrace.NewError("Query returned %d Operations when only 0 or 1 was expected", len(vertiports))
	}
	if len(vertiports) == 0 {
		return nil, nil
	}
	return vertiports[0], nil
}

func (s *repo) fetchVertiportByID(ctx context.Context, q dsssql.Queryable, id dssmodels.ID) (*vrpmodels.Vertiport, error) {
	query := fmt.Sprintf(`
		SELECT %s FROM
			vrp_vertiports
		WHERE
			id = $1`, vertiportFieldsWithoutPrefix)
	uid, err := id.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	return s.fetchVertiport(ctx, q, query, uid)
}

func (s *repo) GetVertiport(ctx context.Context, id dssmodels.ID) (*vrpmodels.Vertiport, error) {
	return s.fetchVertiportByID(ctx, s.q, id)
}

func (s *repo) DeleteVertiport(ctx context.Context, id dssmodels.ID) error {
	var (
		deleteOperationQuery = `
			DELETE FROM
				vrp_vertiports
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
		return stacktrace.NewError("Could not delete Vertiport that does not exist")
	}

	return nil
}

func (s *repo) UpsertVertiport(ctx context.Context, vertiport *vrpmodels.Vertiport) (*vrpmodels.Vertiport, error) {
	var (
		upsertOperationsQuery = fmt.Sprintf(`
			UPSERT INTO
				vrp_vertiports
				(%s)
			VALUES
				($1, $2)
			RETURNING
				%s`, vertiportFieldsWithoutPrefix, vertiportFieldsWithPrefix)
	)

	opid, err := vertiport.ID.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	vertiport, err = s.fetchVertiport(ctx, s.q, upsertOperationsQuery,
		opid,
		vertiport.NumberOfParkingPlaces,
	)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Operation")
	}

	return vertiport, nil
}
