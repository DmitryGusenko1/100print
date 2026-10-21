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
