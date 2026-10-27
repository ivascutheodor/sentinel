--  Schema export from drawDB

CREATE TYPE "roles" AS ENUM (
	'admin',
	'user'
);

CREATE TYPE "capture_states" AS ENUM (
	'capturing',
	'completed',
	'interrupted'
);

CREATE TYPE "video_status" AS ENUM (
	'pending',
	'ready',
	'failed',
	'deleting',
	'deleted'
);

CREATE TYPE "media_status" AS ENUM (
	'queued',
	'running',
	'succeeded',
	'failed',
	'cancelled'
);

CREATE TYPE "event_types" AS ENUM (
	'person_presence'
);

CREATE TYPE "audit_outcomes" AS ENUM (
	'success',
	'denied',
	'failure'
);

CREATE TABLE IF NOT EXISTS "users" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	"display_name" TEXT NOT NULL CHECK(length(btrim(display_name)) BETWEEN 1 AND 200),
	-- Login name: 3-50 lower-case letters, digits, dot, underscore or hyphen. UNIQUE enforces the canonical identity.
	"username" TEXT NOT NULL UNIQUE CHECK(username ~ '^[a-z0-9._-]{3,50}$'),
	-- Encoded password hash, including algorithm and parameters. Hash with Argon2id in the authentication service; never store plaintext.
	"password_hash" TEXT NOT NULL CHECK(length(btrim(password_hash)) > 0),
	"role" ROLES NOT NULL DEFAULT 'user',
	"is_active" BOOLEAN NOT NULL DEFAULT true,
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	"updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id")
);

COMMENT ON TABLE "users" IS 'Single-clinic accounts. Deactivate rather than hard-delete accounts referenced by historical records. Authentication must check is_active. A role change or deactivation also invalidates affected sessions/live authorizations.';
COMMENT ON COLUMN "users"."username" IS 'Login name: 3-50 lower-case letters, digits, dot, underscore or hyphen. UNIQUE enforces the canonical identity.';
COMMENT ON COLUMN "users"."password_hash" IS 'Encoded password hash, including algorithm and parameters. Hash with Argon2id in the authentication service; never store plaintext.';

CREATE TABLE IF NOT EXISTS "cameras" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	"name" TEXT NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 200),
	-- Physical camera location
	"location" TEXT,
	-- RTSP URL configured through the admin UI, without embedded username/password or secret query parameters. Backend parses and validates host/port/path and applies the installation network policy. Exact URL is UNIQUE; credentials are resolved separately. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.
	"stream_url" TEXT NOT NULL UNIQUE CHECK((stream_url ~ '^rtsp://[^/@[:space:]#?]+(/[^[:space:]#]*)?$') AND ((jsonb_typeof(detection_config) = 'object'
AND detection_config ?& ARRAY['schema_version','region']
AND detection_config->'schema_version' = '1'::jsonb
AND (detection_config - 'schema_version' - 'region') = '{}'::jsonb
AND (detection_config->'region' = 'null'::jsonb OR
 (jsonb_typeof(detection_config->'region') = 'object'
  AND (detection_config->'region') ?& ARRAY['type','points','match_rule']
  AND detection_config->'region'->>'type' = 'polygon'
  AND detection_config->'region'->>'match_rule' = 'bottom_center'
  AND ((detection_config->'region') - 'type' - 'points' - 'match_rule') = '{}'::jsonb
  AND CASE WHEN jsonb_typeof(detection_config->'region'->'points') = 'array'
      THEN jsonb_array_length(detection_config->'region'->'points') BETWEEN 3 AND 16
      ELSE false END))) IS TRUE)),
	-- Optional key in the installation secret store containing camera username/password. The secret store is backed up separately; its encryption key is never stored in this database.
	"credentials_ref" TEXT CHECK(credentials_ref IS NULL OR credentials_ref ~ '^[a-z][a-z0-9_]{0,63}$'),
	-- Enable monitoring after URL, credentials, ROI and connectivity validation.
	"is_enabled" BOOLEAN NOT NULL DEFAULT false,
	-- Per-camera ROI only. Confidence and recording timings remain global. SQL validates envelope; backend AND worker must also validate coordinates and polygon geometry (see contract note). SQL invariant is included in the table-wide CHECK anchored to stream_url.
	"detection_config" JSONB NOT NULL DEFAULT jsonb_build_object('schema_version', 1, 'region', NULL),
	-- Server UTC time of last successfully received/decoded frame. Operational heartbeat, not recorded media time.
	"last_frame_at" TIMESTAMPTZ,
	-- Server UTC time of last completed inference. Also monitor frame timestamp lag: successful but stale inference is not healthy real-time analysis.
	"last_inference_at" TIMESTAMPTZ,
	"last_error_code" TEXT,
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	"updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id")
);

COMMENT ON TABLE "cameras" IS 'Single-clinic camera identity survives changes of name, address and credentials. Exactly one recorder owns a camera at a time. Source/ROI changes while capturing require an audited stop/restart; do not silently change an open event. Set is_enabled=false to stop monitoring; this does not by itself revoke archival access.';
COMMENT ON COLUMN "cameras"."location" IS 'Physical camera location';
COMMENT ON COLUMN "cameras"."stream_url" IS 'RTSP URL configured through the admin UI, without embedded username/password or secret query parameters. Backend parses and validates host/port/path and applies the installation network policy. Exact URL is UNIQUE; credentials are resolved separately. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.';
COMMENT ON COLUMN "cameras"."credentials_ref" IS 'Optional key in the installation secret store containing camera username/password. The secret store is backed up separately; its encryption key is never stored in this database.';
COMMENT ON COLUMN "cameras"."is_enabled" IS 'Enable monitoring after URL, credentials, ROI and connectivity validation.';
COMMENT ON COLUMN "cameras"."detection_config" IS 'Per-camera ROI only. Confidence and recording timings remain global. SQL validates envelope; backend AND worker must also validate coordinates and polygon geometry (see contract note). SQL invariant is included in the table-wide CHECK anchored to stream_url.';
COMMENT ON COLUMN "cameras"."last_frame_at" IS 'Server UTC time of last successfully received/decoded frame. Operational heartbeat, not recorded media time.';
COMMENT ON COLUMN "cameras"."last_inference_at" IS 'Server UTC time of last completed inference. Also monitor frame timestamp lag: successful but stale inference is not healthy real-time analysis.';

CREATE TABLE IF NOT EXISTS "events" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	"camera_id" UUID NOT NULL,
	"event_type" EVENT_TYPES NOT NULL DEFAULT 'person_presence',
	"status" CAPTURE_STATES NOT NULL DEFAULT 'capturing',
	-- Timestamp of the first detected person in this presence event; excludes video pre-roll.
	"started_at" TIMESTAMPTZ NOT NULL,
	-- Timestamp of the most recent person detection. Initialize to started_at and update while capturing.
	"last_person_seen_at" TIMESTAMPTZ NOT NULL,
	-- Timestamp when the system closes the event. NULL while capturing; required for completed or interrupted events. Actual video coverage is recorded separately.
	"closed_at" TIMESTAMPTZ,
	-- State/reason and timestamp consistency. Terminal events cannot be reopened (SQL trigger). Source timestamps must be mapped to coherent UTC before comparison. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.
	"end_reason" TEXT CHECK((last_person_seen_at >= started_at
AND (closed_at IS NULL OR closed_at >= last_person_seen_at)
AND ((status = 'capturing' AND closed_at IS NULL AND end_reason IS NULL)
 OR (status = 'completed' AND closed_at IS NOT NULL AND end_reason IS NOT NULL AND end_reason = 'person_absent')
 OR (status = 'interrupted' AND closed_at IS NOT NULL AND end_reason IS NOT NULL
     AND end_reason IN ('stream_lost','worker_restart','manual_stop','camera_disabled','inference_stalled','recording_failed')))) AND ((jsonb_typeof(config_snapshot) = 'object'
AND config_snapshot ?& ARRAY['schema_version','model_ref','detection_config','settings']
AND config_snapshot->'schema_version' = '1'::jsonb
AND jsonb_typeof(config_snapshot->'model_ref') = 'string'
AND length(btrim(config_snapshot->>'model_ref')) > 0
AND jsonb_typeof(config_snapshot->'detection_config') = 'object'
AND jsonb_typeof(config_snapshot->'settings') = 'object') IS TRUE)),
	-- Time the event row is created. started_at is the triggering frame time.
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	-- Immutable snapshot of the validated effective model artifact ID, ROI and recording settings at event start. Full nested validation is shared by backend and worker. Do not include credentials/URLs. See event contract note. SQL invariant is included in the table-wide CHECK anchored to end_reason.
	"config_snapshot" JSONB NOT NULL,
	PRIMARY KEY("id")
);

COMMENT ON TABLE "events" IS 'One continuous presence interval per camera, including overlapping people. Required partial unique index limits capturing events to one per camera (implemented in companion SQL). Snapshot settings at start; terminal event does not imply all clips are ready. Keep event metadata after video retention.';
COMMENT ON COLUMN "events"."started_at" IS 'Timestamp of the first detected person in this presence event; excludes video pre-roll.';
COMMENT ON COLUMN "events"."last_person_seen_at" IS 'Timestamp of the most recent person detection. Initialize to started_at and update while capturing.';
COMMENT ON COLUMN "events"."closed_at" IS 'Timestamp when the system closes the event. NULL while capturing; required for completed or interrupted events. Actual video coverage is recorded separately.';
COMMENT ON COLUMN "events"."end_reason" IS 'State/reason and timestamp consistency. Terminal events cannot be reopened (SQL trigger). Source timestamps must be mapped to coherent UTC before comparison. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.';
COMMENT ON COLUMN "events"."created_at" IS 'Time the event row is created. started_at is the triggering frame time.';
COMMENT ON COLUMN "events"."config_snapshot" IS 'Immutable snapshot of the validated effective model artifact ID, ROI and recording settings at event start. Full nested validation is shared by backend and worker. Do not include credentials/URLs. See event contract note. SQL invariant is included in the table-wide CHECK anchored to end_reason.';

CREATE INDEX "ix_events_camera_id_started_at"
ON "events" ("camera_id", "started_at");
CREATE INDEX "ix_events_started_at"
ON "events" ("started_at");

CREATE TABLE IF NOT EXISTS "audit_logs" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	-- user for authenticated human actions; system for named services; anonymous for unauthenticated attempts such as failed login.
	"actor_type" TEXT NOT NULL CHECK((actor_type = 'user' AND actor_user_id IS NOT NULL AND actor_service IS NULL)
OR (actor_type = 'system' AND actor_user_id IS NULL AND actor_service IS NOT NULL AND length(btrim(actor_service)) > 0)
OR (actor_type = 'anonymous' AND actor_user_id IS NULL AND actor_service IS NULL)),
	"actor_user_id" UUID,
	"actor_service" TEXT,
	-- Versioned action vocabulary in backend, e.g. camera_access.granted, session.revoked, clip.playback_authorized. Playback authorization does not prove review. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.
	"action" TEXT NOT NULL CHECK((length(btrim(action)) > 0) AND (details IS NULL OR jsonb_typeof(details) = 'object')),
	"resource_type" TEXT,
	-- Polymorphic identifier serialized to canonical text (UUID resources or system_settings id=1). Intentionally no FK: audit entries outlive resource deletion.
	"resource_id" TEXT CHECK((resource_type IS NULL AND resource_id IS NULL)
OR (resource_type IS NOT NULL AND resource_id IS NOT NULL AND length(btrim(resource_type)) > 0 AND length(btrim(resource_id)) > 0)),
	"outcome" AUDIT_OUTCOMES NOT NULL,
	"occurred_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	"request_id" UUID,
	-- Sanitized structured context including grant target, before/after settings and failure codes. Never include passwords, tokens or camera credentials. SQL invariant is included in the table-wide CHECK anchored to action.
	"details" JSONB,
	PRIMARY KEY("id")
);

COMMENT ON TABLE "audit_logs" IS 'Append-only application history; companion SQL rejects UPDATE/DELETE/TRUNCATE. Runtime role must not own tables or disable triggers. Retention/export is a separately authorized owner maintenance procedure. User FKs use NO ACTION and users are normally deactivated. Audit and event-metadata retention are separate from video retention.';
COMMENT ON COLUMN "audit_logs"."actor_type" IS 'user for authenticated human actions; system for named services; anonymous for unauthenticated attempts such as failed login.';
COMMENT ON COLUMN "audit_logs"."action" IS 'Versioned action vocabulary in backend, e.g. camera_access.granted, session.revoked, clip.playback_authorized. Playback authorization does not prove review. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.';
COMMENT ON COLUMN "audit_logs"."resource_id" IS 'Polymorphic identifier serialized to canonical text (UUID resources or system_settings id=1). Intentionally no FK: audit entries outlive resource deletion.';
COMMENT ON COLUMN "audit_logs"."details" IS 'Sanitized structured context including grant target, before/after settings and failure codes. Never include passwords, tokens or camera credentials. SQL invariant is included in the table-wide CHECK anchored to action.';

CREATE INDEX "ix_audit_logs_occurred_at"
ON "audit_logs" ("occurred_at");
CREATE INDEX "ix_audit_logs_actor_user_id_occurred_at"
ON "audit_logs" ("actor_user_id", "occurred_at");
CREATE INDEX "ix_audit_logs_resource_type_resource_id_occurred_at"
ON "audit_logs" ("resource_type", "resource_id", "occurred_at");

CREATE TABLE IF NOT EXISTS "video_clips" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	"event_id" UUID NOT NULL,
	-- Positive part number, UNIQUE with event_id. Allocated transactionally by the camera recorder. Numeric gaps are allowed after interrupted processing.
	"part_number" INTEGER NOT NULL CHECK(part_number >= 1),
	-- Stable relative key allocated at clip creation, e.g. manifests/<clip_id>.json. Manifest persists target time range, pinned source segments and their checksums/timestamps; it must survive worker restart. No user-controlled path.
	"source_manifest_ref" TEXT NOT NULL UNIQUE CHECK(length(btrim(source_manifest_ref)) > 0),
	-- Set only after sealed input manifest and source segments are durably available. Queue finalize_clip in the same DB transaction. Reconcile a sealed manifest left behind before this commit.
	"source_ready_at" TIMESTAMPTZ,
	-- Verified actual first media time, excluding unavailable buffer. Can be NULL before finalization.
	"recorded_start_at" TIMESTAMPTZ,
	-- Verified actual end of media coverage; greater than recorded_start_at. Intervals are half-open [start,end). Internal gaps are recorded in the manifest; avoid pretending interrupted streams were continuous. SQL invariant is included in the table-wide CHECK anchored to filepath.
	"recorded_end_at" TIMESTAMPTZ,
	-- Private storage-relative key of the immutable output object, unique per attempt. Backend resolves and authorizes playback; never expose a server filesystem path as a browser URL. Retain key in deleted metadata. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.
	"filepath" TEXT UNIQUE CHECK(((filepath IS NULL OR length(btrim(filepath)) > 0)
AND (status <> 'ready' OR (filepath IS NOT NULL AND size_bytes IS NOT NULL AND size_bytes > 0
 AND recorded_start_at IS NOT NULL AND recorded_end_at IS NOT NULL AND source_ready_at IS NOT NULL))) AND ((recorded_start_at IS NULL AND recorded_end_at IS NULL) OR (recorded_start_at IS NOT NULL AND recorded_end_at IS NOT NULL AND recorded_end_at > recorded_start_at)) AND ((status IN ('deleting','deleted') AND delete_requested_at IS NOT NULL) OR (status NOT IN ('deleting','deleted') AND delete_requested_at IS NULL)) AND ((status = 'deleted' AND deleted_at IS NOT NULL AND deleted_at >= delete_requested_at) OR (status <> 'deleted' AND deleted_at IS NULL))),
	"size_bytes" BIGINT CHECK(size_bytes IS NULL OR size_bytes > 0),
	-- Optional lowercase SHA-256 of the final video. Verifies byte integrity, not provenance by itself.
	"sha256" TEXT CHECK(sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'),
	"status" VIDEO_STATUS NOT NULL DEFAULT 'pending',
	-- Required for failed media generation. Job-level transient/deletion failures belong in media_jobs.last_error_code.
	"failure_code" TEXT CHECK((failure_code IS NULL OR length(btrim(failure_code)) > 0)
AND (status <> 'failed' OR failure_code IS NOT NULL)
AND (status NOT IN ('pending','ready') OR failure_code IS NULL)),
	-- Access deadline persisted using the event snapshot retention_days. Start with created_at + retention; on seal use the final target media end + retention, then after verification use recorded_end_at + retention. Never reset expiry to processing/retry time. If already expired, delete instead of publishing.
	"expires_at" TIMESTAMPTZ NOT NULL,
	-- Irreversible logical deletion request: revoke access, cancel finalization and queue deletion in one transaction. Capture/seal an in-progress part before deleting its shared input. SQL invariant is included in the table-wide CHECK anchored to filepath.
	"delete_requested_at" TIMESTAMPTZ,
	-- Set when known output/temporary objects are absent and source references released. Keep row for history. Reconciliation removes any late orphan output. SQL invariant is included in the table-wide CHECK anchored to filepath.
	"deleted_at" TIMESTAMPTZ,
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	"updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id"),
	CONSTRAINT "uq_video_clips_event_part" UNIQUE ("event_id", "part_number")
);

COMMENT ON TABLE "video_clips" IS 'Clip lifecycle: pending -> ready/failed/deleting; failed -> pending (explicit retry) or deleting; ready -> failed (verified missing/corrupt file) or deleting; deleting -> deleted; deleted is terminal. Required SQL triggers enforce transitions. A source manifest identifies recoverable input even while pending. Finalization and deletion are serialized using clip row locking plus valid job token; database transactions never include the full video processing duration.';
COMMENT ON COLUMN "video_clips"."part_number" IS 'Positive part number, UNIQUE with event_id. Allocated transactionally by the camera recorder. Numeric gaps are allowed after interrupted processing.';
COMMENT ON COLUMN "video_clips"."source_manifest_ref" IS 'Stable relative key allocated at clip creation, e.g. manifests/<clip_id>.json. Manifest persists target time range, pinned source segments and their checksums/timestamps; it must survive worker restart. No user-controlled path.';
COMMENT ON COLUMN "video_clips"."source_ready_at" IS 'Set only after sealed input manifest and source segments are durably available. Queue finalize_clip in the same DB transaction. Reconcile a sealed manifest left behind before this commit.';
COMMENT ON COLUMN "video_clips"."recorded_start_at" IS 'Verified actual first media time, excluding unavailable buffer. Can be NULL before finalization.';
COMMENT ON COLUMN "video_clips"."recorded_end_at" IS 'Verified actual end of media coverage; greater than recorded_start_at. Intervals are half-open [start,end). Internal gaps are recorded in the manifest; avoid pretending interrupted streams were continuous. SQL invariant is included in the table-wide CHECK anchored to filepath.';
COMMENT ON COLUMN "video_clips"."filepath" IS 'Private storage-relative key of the immutable output object, unique per attempt. Backend resolves and authorizes playback; never expose a server filesystem path as a browser URL. Retain key in deleted metadata. Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.';
COMMENT ON COLUMN "video_clips"."sha256" IS 'Optional lowercase SHA-256 of the final video. Verifies byte integrity, not provenance by itself.';
COMMENT ON COLUMN "video_clips"."failure_code" IS 'Required for failed media generation. Job-level transient/deletion failures belong in media_jobs.last_error_code.';
COMMENT ON COLUMN "video_clips"."expires_at" IS 'Access deadline persisted using the event snapshot retention_days. Start with created_at + retention; on seal use the final target media end + retention, then after verification use recorded_end_at + retention. Never reset expiry to processing/retry time. If already expired, delete instead of publishing.';
COMMENT ON COLUMN "video_clips"."delete_requested_at" IS 'Irreversible logical deletion request: revoke access, cancel finalization and queue deletion in one transaction. Capture/seal an in-progress part before deleting its shared input. SQL invariant is included in the table-wide CHECK anchored to filepath.';
COMMENT ON COLUMN "video_clips"."deleted_at" IS 'Set when known output/temporary objects are absent and source references released. Keep row for history. Reconciliation removes any late orphan output. SQL invariant is included in the table-wide CHECK anchored to filepath.';

CREATE INDEX "ix_video_clips_status_expires_at"
ON "video_clips" ("status", "expires_at");

CREATE TABLE IF NOT EXISTS "media_jobs" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	"clip_id" UUID NOT NULL,
	-- One logical job per (clip_id,job_type). Retries update the same row; administrative retries extend max_attempts and are audited.
	"job_type" TEXT NOT NULL CHECK(job_type IN ('finalize_clip','delete_clip')),
	"status" MEDIA_STATUS NOT NULL DEFAULT 'queued',
	-- Increment atomically when claimed; must not exceed max_attempts. A claim must verify input readiness, clip lifecycle and expiry.
	"attempt_count" INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0 AND attempt_count <= max_attempts
AND (status NOT IN ('running','succeeded') OR attempt_count >= 1)
AND ((status = 'running' AND lock_token IS NOT NULL AND locked_until IS NOT NULL)
 OR (status <> 'running' AND lock_token IS NULL AND locked_until IS NULL))
AND (status <> 'failed' OR last_error_code IS NOT NULL)),
	-- Proposed retry budget, configurable per job. Exhausted delete jobs leave clip deleting/inaccessible and raise an operational alert.
	"max_attempts" INTEGER NOT NULL DEFAULT 5 CHECK(max_attempts > 0),
	-- Not eligible before this time. Use bounded exponential retry backoff; retries preserve the logical job id.
	"available_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	-- Fresh random fencing token for each claim. Heartbeat and completion must compare this token; an expired worker cannot publish.
	"lock_token" UUID,
	-- Renewable lease expiry. Reclaim expired jobs under locks; never infer a dead worker from status alone.
	"locked_until" TIMESTAMPTZ,
	-- Sanitized machine-readable error; no RTSP credentials, raw session token or full untrusted command output.
	"last_error_code" TEXT CHECK(last_error_code IS NULL OR length(btrim(last_error_code)) > 0),
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	"updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id"),
	CONSTRAINT "uq_media_jobs_clip_type" UNIQUE ("clip_id", "job_type")
);

COMMENT ON TABLE "media_jobs" IS 'At-least-once work queue, not exactly-once external side effects. UNIQUE(clip_id,job_type) prevents duplicate logical jobs. Required partial unique index allows at most one running job per clip across all types. Lease/token checks, deterministic manifests, immutable attempt outputs and reconciliation provide safe retries. Acquire clip then job locks in consistent order; see worker protocol note.';
COMMENT ON COLUMN "media_jobs"."job_type" IS 'One logical job per (clip_id,job_type). Retries update the same row; administrative retries extend max_attempts and are audited.';
COMMENT ON COLUMN "media_jobs"."attempt_count" IS 'Increment atomically when claimed; must not exceed max_attempts. A claim must verify input readiness, clip lifecycle and expiry.';
COMMENT ON COLUMN "media_jobs"."max_attempts" IS 'Proposed retry budget, configurable per job. Exhausted delete jobs leave clip deleting/inaccessible and raise an operational alert.';
COMMENT ON COLUMN "media_jobs"."available_at" IS 'Not eligible before this time. Use bounded exponential retry backoff; retries preserve the logical job id.';
COMMENT ON COLUMN "media_jobs"."lock_token" IS 'Fresh random fencing token for each claim. Heartbeat and completion must compare this token; an expired worker cannot publish.';
COMMENT ON COLUMN "media_jobs"."locked_until" IS 'Renewable lease expiry. Reclaim expired jobs under locks; never infer a dead worker from status alone.';
COMMENT ON COLUMN "media_jobs"."last_error_code" IS 'Sanitized machine-readable error; no RTSP credentials, raw session token or full untrusted command output.';

CREATE INDEX "ix_media_jobs_status_available_at_created_at"
ON "media_jobs" ("status", "available_at", "created_at");
CREATE INDEX "ix_media_jobs_status_locked_until"
ON "media_jobs" ("status", "locked_until");

CREATE TABLE IF NOT EXISTS "system_settings" (
	-- Exactly one configured row, id=1. CHECK/PK allow at most one; bootstrap SQL inserts it and a trigger prevents its removal.
	"id" SMALLINT NOT NULL DEFAULT 1 CHECK(id = 1),
	"retention_days" INTEGER NOT NULL DEFAULT 7 CHECK(retention_days > 0),
	"pre_roll_seconds" INTEGER NOT NULL DEFAULT 10 CHECK(pre_roll_seconds >= 0),
	-- V1: both absence grace and video tail after the last accepted presence. Close only once healthy analysis has covered this interval. Do not add this interval twice. Zero means close at the next confirmed absence.
	"post_roll_seconds" INTEGER NOT NULL DEFAULT 10 CHECK(post_roll_seconds >= 0),
	"clip_part_seconds" INTEGER NOT NULL DEFAULT 60 CHECK(clip_part_seconds > 0),
	"confidence_threshold" DOUBLE PRECISION NOT NULL DEFAULT 0.60 CHECK(confidence_threshold >= 0 AND confidence_threshold <= 1),
	-- Proposed absolute session lifetime: 12 hours, applied at login.
	"session_absolute_seconds" INTEGER NOT NULL DEFAULT 43200 CHECK(session_absolute_seconds > 0),
	-- Proposed inactivity timeout: 30 minutes; live viewing needs authenticated activity/heartbeat. Revocation delivery is independent of heartbeat.
	"session_idle_seconds" INTEGER NOT NULL DEFAULT 1800 CHECK(session_idle_seconds > 0 AND session_idle_seconds <= session_absolute_seconds),
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	"updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id")
);

COMMENT ON TABLE "system_settings" IS 'Singleton per installation, not per camera. Seed values are initial engineering defaults: retention 7 days, pre/post 10 seconds, parts 60 seconds, confidence 0.60; admin must review for deployment. Updates affect newly created events. Existing events use config_snapshot; existing clip expiries are not silently rewritten. Controlled retention changes on existing data require a separate audited operation.';
COMMENT ON COLUMN "system_settings"."id" IS 'Exactly one configured row, id=1. CHECK/PK allow at most one; bootstrap SQL inserts it and a trigger prevents its removal.';
COMMENT ON COLUMN "system_settings"."post_roll_seconds" IS 'V1: both absence grace and video tail after the last accepted presence. Close only once healthy analysis has covered this interval. Do not add this interval twice. Zero means close at the next confirmed absence.';
COMMENT ON COLUMN "system_settings"."session_absolute_seconds" IS 'Proposed absolute session lifetime: 12 hours, applied at login.';
COMMENT ON COLUMN "system_settings"."session_idle_seconds" IS 'Proposed inactivity timeout: 30 minutes; live viewing needs authenticated activity/heartbeat. Revocation delivery is independent of heartbeat.';

CREATE TABLE IF NOT EXISTS "camera_access" (
	"user_id" UUID NOT NULL,
	"camera_id" UUID NOT NULL,
	"granted_by" UUID NOT NULL,
	"granted_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("user_id", "camera_id")
);

COMMENT ON TABLE "camera_access" IS 'Composite PRIMARY KEY(user_id,camera_id). Both parent relationships are many-to-one. Active admins access all cameras; active users access only assigned cameras and their events/clips. Grant/revoke is authorized and audited by backend. Revoking access terminates affected active streams.';

CREATE INDEX "ix_camera_access_camera_id_user_id"
ON "camera_access" ("camera_id", "user_id");

CREATE TABLE IF NOT EXISTS "user_sessions" (
	"id" UUID NOT NULL DEFAULT gen_random_uuid(),
	"user_id" UUID NOT NULL,
	-- SHA-256 of an opaque cryptographically random session token with at least 256 bits of entropy. Never a hash of the user password. Raw token only in the protected cookie. SQL invariant is included in the table-wide CHECK anchored to user_agent.
	"token_hash" BYTEA NOT NULL UNIQUE,
	"created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	-- Last authenticated activity, periodically persisted. Not proof that a physical device is currently online. SQL invariant is included in the table-wide CHECK anchored to user_agent.
	"last_seen_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
	-- Absolute deadline calculated at login from system_settings.session_absolute_seconds. Validate inactivity separately. SQL invariant is included in the table-wide CHECK anchored to user_agent.
	"expires_at" TIMESTAMPTZ NOT NULL,
	-- NULL until revoked; a system revocation may have no revoked_by_user_id. SQL invariant is included in the table-wide CHECK anchored to user_agent.
	"revoked_at" TIMESTAMPTZ,
	"revoked_by_user_id" UUID,
	--  Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.
	"user_agent" TEXT CHECK((octet_length(token_hash) = 32) AND (last_seen_at >= created_at) AND (expires_at > created_at) AND ((revoked_at IS NULL OR revoked_at >= created_at) AND (revoked_by_user_id IS NULL OR revoked_at IS NOT NULL))),
	"last_ip" INET,
	PRIMARY KEY("id")
);

COMMENT ON TABLE "user_sessions" IS 'One row per authenticated browser session. Backend checks token hash, user activity, revocation, absolute expiry and idle timeout for every protected operation. Revocation must propagate to active video and WebSocket connections. User-agent is descriptive, not a physical-device identifier.';
COMMENT ON COLUMN "user_sessions"."token_hash" IS 'SHA-256 of an opaque cryptographically random session token with at least 256 bits of entropy. Never a hash of the user password. Raw token only in the protected cookie. SQL invariant is included in the table-wide CHECK anchored to user_agent.';
COMMENT ON COLUMN "user_sessions"."last_seen_at" IS 'Last authenticated activity, periodically persisted. Not proof that a physical device is currently online. SQL invariant is included in the table-wide CHECK anchored to user_agent.';
COMMENT ON COLUMN "user_sessions"."expires_at" IS 'Absolute deadline calculated at login from system_settings.session_absolute_seconds. Validate inactivity separately. SQL invariant is included in the table-wide CHECK anchored to user_agent.';
COMMENT ON COLUMN "user_sessions"."revoked_at" IS 'NULL until revoked; a system revocation may have no revoked_by_user_id. SQL invariant is included in the table-wide CHECK anchored to user_agent.';
COMMENT ON COLUMN "user_sessions"."user_agent" IS ' Includes cross-column CHECK expressions here for drawDB PostgreSQL export compatibility.';

CREATE INDEX "ix_user_sessions_user_id_created_at"
ON "user_sessions" ("user_id", "created_at");
CREATE INDEX "ix_user_sessions_expires_at"
ON "user_sessions" ("expires_at");

ALTER TABLE "events"
ADD FOREIGN KEY("camera_id") REFERENCES "cameras"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "video_clips"
ADD FOREIGN KEY("event_id") REFERENCES "events"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "audit_logs"
ADD FOREIGN KEY("actor_user_id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "media_jobs"
ADD FOREIGN KEY("clip_id") REFERENCES "video_clips"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "camera_access"
ADD FOREIGN KEY("user_id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE CASCADE;
ALTER TABLE "camera_access"
ADD FOREIGN KEY("camera_id") REFERENCES "cameras"("id")
ON UPDATE NO ACTION ON DELETE CASCADE;
ALTER TABLE "camera_access"
ADD FOREIGN KEY("granted_by") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE NO ACTION;
ALTER TABLE "user_sessions"
ADD FOREIGN KEY("revoked_by_user_id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE SET NULL;
ALTER TABLE "user_sessions"
ADD FOREIGN KEY("user_id") REFERENCES "users"("id")
ON UPDATE NO ACTION ON DELETE CASCADE;