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
	"github.com/jackc/pgx/v4"
)

const (
	nConstraintFields = 9
)

var (
	constraintFieldsWithIndices   [nConstraintFields]string
	constraintFieldsWithPrefix    string
	constraintFieldsWithoutPrefix string
)

// TODO Update database schema and fields below.
func init() {
	constraintFieldsWithIndices[0] = "id"
	constraintFieldsWithIndices[1] = "owner"
	constraintFieldsWithIndices[2] = "version"
	constraintFieldsWithIndices[3] = "url"
	constraintFieldsWithIndices[4] = "vertiport_id"
	constraintFieldsWithIndices[5] = "vertiport_zone"
	constraintFieldsWithIndices[6] = "starts_at"
	constraintFieldsWithIndices[7] = "ends_at"
	constraintFieldsWithIndices[8] = "updated_at"

	constraintFieldsWithoutPrefix = strings.Join(
		constraintFieldsWithIndices[:], ",",
	)

	withPrefix := make([]string, nConstraintFields)
	for idx, field := range constraintFieldsWithIndices {
		withPrefix[idx] = "vrp_constraints." + field
	}

	constraintFieldsWithPrefix = strings.Join(
		withPrefix[:], ",",
	)
}

func (c *repo) fetchConstraints(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) ([]*vrpmodels.VertiportConstraint, error) {
	rows, err := q.Query(ctx, query, args...)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error in query: %s", query)
	}
	defer rows.Close()

	var payload []*vrpmodels.VertiportConstraint
	for rows.Next() {
		var (
			c         = new(vrpmodels.VertiportConstraint)
			updatedAt time.Time
		)
		err := rows.Scan(
			&c.ID,
			&c.Manager,
			&c.Version,
			&c.USSBaseURL,
			&c.VertiportID,
			&c.VertiportZone,
			&c.StartTime,
			&c.EndTime,
			&updatedAt,
		)
		if err != nil {
			return nil, stacktrace.Propagate(err, "Error scanning Constraint row")
		}
		c.OVN = vrpmodels.NewOVNFromTime(updatedAt, c.ID.String())
		payload = append(payload, c)
	}
	if err := rows.Err(); err != nil {
		return nil, stacktrace.Propagate(err, "Error in rows query result")
	}
	return payload, nil
}

func (c *repo) fetchConstraint(ctx context.Context, q dsssql.Queryable, query string, args ...interface{}) (*vrpmodels.VertiportConstraint, error) {
	constraints, err := c.fetchConstraints(ctx, q, query, args...)
	if err != nil {
		return nil, err // No need to Propagate this error as this stack layer does not add useful information
	}
	if len(constraints) > 1 {
		return nil, stacktrace.NewError("Query returned %d Constraints when only 0 or 1 was expected", len(constraints))
	}
	if len(constraints) == 0 {
		return nil, pgx.ErrNoRows
	}
	return constraints[0], nil
}

// Implements scd.repos.Constraint.GetConstraint
func (c *repo) GetVertiportConstraint(ctx context.Context, id dssmodels.ID) (*vrpmodels.VertiportConstraint, error) {
	var (
		query = fmt.Sprintf(`
			SELECT
				%s
			FROM
				vrp_constraints
			WHERE
				id = $1`, constraintFieldsWithoutPrefix)
	)
	uid, err := id.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	return c.fetchConstraint(ctx, c.q, query, uid)
}

// Implements scd.repos.Constraint.UpsertConstraint
func (c *repo) UpsertVertiportConstraint(ctx context.Context, s *vrpmodels.VertiportConstraint) (*vrpmodels.VertiportConstraint, error) {
	var (
		upsertQuery = fmt.Sprintf(`
		UPSERT INTO
		  vrp_constraints
		  (%s)
		VALUES
			($1, $2, $3, $4, $5, $6, $7, $8, transaction_timestamp())
		RETURNING
			%s`, constraintFieldsWithoutPrefix, constraintFieldsWithPrefix)
	)

	id, err := s.ID.PgUUID()
	if err != nil {
		return nil, stacktrace.Propagate(err, "Failed to convert id to PgUUID")
	}
	s, err = c.fetchConstraint(ctx, c.q, upsertQuery,
		id,
		s.Manager,
		s.Version,
		s.USSBaseURL,
		s.VertiportID,
		s.VertiportZone,
		s.StartTime,
		s.EndTime,
	)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Constraint")
	}

	return s, nil
}

// Implements scd.repos.Constraint.DeleteConstraint
func (c *repo) DeleteVertiportConstraint(ctx context.Context, id dssmodels.ID) error {
	const (
		query = `
		DELETE FROM
			vrp_constraints
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
		return pgx.ErrNoRows
	}

	return nil
}

// Implements scd.repos.Constraint.SearchConstraints
func (c *repo) SearchVertiportConstraints(ctx context.Context, reservation *dssmodels.VertiportReservation) ([]*vrpmodels.VertiportConstraint, error) {
	var (
		query = fmt.Sprintf(`
			SELECT
				%s
			FROM
				vrp_constraints
			WHERE
			  vertiport_id = $1 AND vertiport_zone = $2
			AND
				COALESCE(starts_at <= $4, true)
			AND
				COALESCE(ends_at >= $3, true)
			LIMIT $4`, constraintFieldsWithoutPrefix)
	)

	constraints, err := c.fetchConstraints(
		ctx, c.q, query, reservation.VertiportID, reservation.VertiportZone, reservation.StartTime, reservation.EndTime, dssmodels.MaxResultLimit)
	if err != nil {
		return nil, stacktrace.Propagate(err, "Error fetching Constraints")
	}

	return constraints, nil
}
