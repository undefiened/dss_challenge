CREATE TYPE operational_intent_state AS ENUM ('Unknown', 'Accepted', 'Activated', 'Nonconforming', 'Contingent');

CREATE TABLE IF NOT EXISTS vrp_subscriptions (
  id UUID PRIMARY KEY,
  owner STRING NOT NULL,
  version INT4 NOT NULL DEFAULT 0,
  url STRING NOT NULL,
  notification_index INT4 DEFAULT 0,
  notify_for_operations BOOL DEFAULT false,
  notify_for_constraints BOOL DEFAULT false,
  implicit BOOL DEFAULT false,
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  vertiport_id STRING NOT NULL,
  vertiport_zone INT8,
  updated_at TIMESTAMPTZ NOT NULL,
  INDEX owner_idx (owner),
  INDEX starts_at_idx (starts_at),
  INDEX ends_at_idx (ends_at),
  CHECK (starts_at IS NULL OR ends_at IS NULL OR starts_at < ends_at),
  CHECK (notify_for_operations OR notify_for_constraints)
);
CREATE TABLE IF NOT EXISTS vrp_operations (
  id UUID PRIMARY KEY,
  owner STRING NOT NULL,
  version INT4 NOT NULL DEFAULT 0,
  url STRING NOT NULL,
  vertiport_id STRING NOT NULL,
  vertiport_zone int8,
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  subscription_id UUID REFERENCES vrp_subscriptions(id) ON DELETE CASCADE,
  updated_at TIMESTAMPTZ NOT NULL,
  state operational_intent_state NOT NULL,
  INDEX owner_idx (owner),
  INDEX starts_at_idx (starts_at),
  INDEX ends_at_idx (ends_at),
  INDEX updated_at_idx (updated_at),
  INDEX subscription_id_idx (subscription_id),
  CHECK (starts_at IS NULL OR ends_at IS NULL OR starts_at < ends_at)
);
CREATE TABLE IF NOT EXISTS vrp_constraints (
  id UUID PRIMARY KEY,
  owner STRING NOT NULL,
  version INT4 NOT NULL DEFAULT 0,
  url STRING NOT NULL,
  vertiport_id STRING NOT NULL,
  vertiport_zone int8,
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL,
  INDEX owner_idx (owner),
  INDEX starts_at_idx (starts_at),
  INDEX ends_at_idx (ends_at),
  CHECK (starts_at IS NULL OR ends_at IS NULL OR starts_at < ends_at)
);

CREATE TABLE IF NOT EXISTS schema_versions (
	onerow_enforcer bool PRIMARY KEY DEFAULT TRUE CHECK(onerow_enforcer),
	schema_version STRING NOT NULL
);

INSERT INTO schema_versions (schema_version) VALUES ('v1.0.0');
