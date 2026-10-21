CREATE TABLE IF NOT EXISTS departments (id text PRIMARY KEY, name text NOT NULL);
CREATE TABLE IF NOT EXISTS agents (id text PRIMARY KEY, department_id text REFERENCES departments(id), enabled boolean NOT NULL DEFAULT true);
CREATE TABLE IF NOT EXISTS tasks (
 id uuid PRIMARY KEY, source text NOT NULL, type text NOT NULL, title text NOT NULL,
 payload jsonb NOT NULL DEFAULT '{}', assigned_to text REFERENCES agents(id),
 status text NOT NULL DEFAULT 'new' CHECK(status IN ('new','processing','done','failed','waiting')),
 priority integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz, finished_at timestamptz, updated_at timestamptz NOT NULL DEFAULT now(),
 error text, result jsonb, attempts integer NOT NULL DEFAULT 0,
 max_attempts integer NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 10),
 available_at timestamptz NOT NULL DEFAULT now(), dedupe_key text UNIQUE
);
CREATE INDEX IF NOT EXISTS tasks_queue ON tasks(priority DESC, created_at) WHERE status='new';
CREATE TABLE IF NOT EXISTS messages (id bigserial PRIMARY KEY, task_id uuid REFERENCES tasks(id), body jsonb NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS agent_runs (id bigserial PRIMARY KEY, task_id uuid REFERENCES tasks(id), agent_id text REFERENCES agents(id), status text NOT NULL, started_at timestamptz DEFAULT now(), finished_at timestamptz, result jsonb, error text);
CREATE TABLE IF NOT EXISTS handoffs (id bigserial PRIMARY KEY, task_id uuid REFERENCES tasks(id), status text NOT NULL DEFAULT 'pending', updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS decisions (id bigserial PRIMARY KEY, task_id uuid REFERENCES tasks(id), body jsonb NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS reports (id bigserial PRIMARY KEY, day date UNIQUE NOT NULL, body jsonb NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS heartbeats (id text PRIMARY KEY, updated_at timestamptz NOT NULL, details jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS scheduler_state (name text PRIMARY KEY, last_run timestamptz NOT NULL);
INSERT INTO departments VALUES ('operations','Operations') ON CONFLICT DO NOTHING;
INSERT INTO agents VALUES ('local','operations',true) ON CONFLICT DO NOTHING;

-- Business organization v1. Queue UUID is the recovery/idempotency boundary.
CREATE TABLE IF NOT EXISTS skills_registry (
 id text NOT NULL, version text NOT NULL, definition jsonb NOT NULL,
 PRIMARY KEY(id,version)
);
CREATE TABLE IF NOT EXISTS organization_roles (id text PRIMARY KEY REFERENCES agents(id), definition jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS organization_steps (
 task_id uuid REFERENCES tasks(id) NOT NULL, step_key text NOT NULL,
 fingerprint text NOT NULL, result jsonb NOT NULL, metadata jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(task_id,step_key)
);
CREATE TABLE IF NOT EXISTS organization_handoffs (
 task_id uuid REFERENCES tasks(id) NOT NULL, handoff_key text NOT NULL,
 body jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(task_id,handoff_key)
);
CREATE TABLE IF NOT EXISTS github_deliveries (
 issue_number integer PRIMARY KEY, task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
 delivered_at timestamptz, comment_url text
);
