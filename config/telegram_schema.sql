CREATE TABLE IF NOT EXISTS telegram_sessions (
 chat_id text NOT NULL, user_id text NOT NULL, conversation_id uuid NOT NULL REFERENCES project_conversations(id),
 PRIMARY KEY(chat_id,user_id)
);
CREATE TABLE IF NOT EXISTS telegram_inbox (
 update_id bigint PRIMARY KEY, chat_id text NOT NULL, user_id text NOT NULL,
 conversation_id uuid NOT NULL REFERENCES project_conversations(id), task_id uuid REFERENCES tasks(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS telegram_outbox (
 id bigserial PRIMARY KEY, update_id bigint NOT NULL REFERENCES telegram_inbox(update_id),
 part integer NOT NULL, text text NOT NULL, state text NOT NULL DEFAULT 'pending'
 CHECK(state IN ('pending','sending','sent','uncertain')), telegram_message_id bigint,
 UNIQUE(update_id,part)
);

ALTER TABLE telegram_outbox ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'final';
ALTER TABLE telegram_outbox ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE telegram_outbox ADD COLUMN IF NOT EXISTS sent_at timestamptz;
ALTER TABLE telegram_outbox DROP CONSTRAINT IF EXISTS telegram_outbox_update_id_part_key;
CREATE UNIQUE INDEX IF NOT EXISTS telegram_outbox_kind_part ON telegram_outbox(update_id,kind,part);
