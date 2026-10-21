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
