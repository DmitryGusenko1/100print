CREATE TABLE IF NOT EXISTS chatgpt_bridge_state (
 issue_number integer PRIMARY KEY CHECK(issue_number=8), last_comment_id bigint NOT NULL DEFAULT 0
);
INSERT INTO chatgpt_bridge_state(issue_number) VALUES (8) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS chatgpt_bridge_comments (
 comment_id bigint PRIMARY KEY, session_id text NOT NULL,
 conversation_id uuid NOT NULL REFERENCES project_conversations(id),
 task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
 created_at timestamptz NOT NULL DEFAULT now(), delivered_at timestamptz,
 reply_comment_id bigint UNIQUE
);
CREATE TABLE IF NOT EXISTS hermes_bridge_jobs (
 task_id uuid PRIMARY KEY REFERENCES tasks(id), session_id text NOT NULL,
 prompt text NOT NULL, status text NOT NULL DEFAULT 'queued'
 CHECK(status IN ('queued','running','awaiting_owner','done','failed')),
 result jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS hermes_bridge_sessions (
 session_id text PRIMARY KEY, hermes_session_id text NOT NULL
);
ALTER TABLE chatgpt_bridge_comments ADD COLUMN IF NOT EXISTS delivery_attempts integer NOT NULL DEFAULT 0;
