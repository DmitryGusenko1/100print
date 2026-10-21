CREATE TABLE IF NOT EXISTS project_conversations (
 id uuid PRIMARY KEY, project_id text NOT NULL DEFAULT '100print' CHECK(project_id='100print'),
 source text NOT NULL CHECK(source IN ('chatgpt','telegram')), external_session_id text NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(), last_activity_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source,external_session_id)
);
CREATE TABLE IF NOT EXISTS project_memory (
 id uuid PRIMARY KEY, project_id text NOT NULL DEFAULT '100print' CHECK(project_id='100print'),
 conversation_id uuid NOT NULL REFERENCES project_conversations(id), task_id uuid REFERENCES tasks(id),
 kind text NOT NULL CHECK(kind IN ('message','decision','action_item','fact','hypothesis','specialist_result','council_round','contradiction','question','constraint','causal_link')),
 role text NOT NULL, text text NOT NULL, source text NOT NULL CHECK(source IN ('chatgpt','telegram','organization')),
 metadata jsonb NOT NULL DEFAULT '{}', importance real NOT NULL CHECK(importance BETWEEN 0 AND 1),
 confidence real NOT NULL CHECK(confidence BETWEEN 0 AND 1), dedupe_key text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 search_vector tsvector GENERATED ALWAYS AS (to_tsvector('russian',text)) STORED,
 UNIQUE(conversation_id,kind,dedupe_key)
);
CREATE INDEX IF NOT EXISTS project_memory_search ON project_memory USING gin(search_vector);
CREATE INDEX IF NOT EXISTS project_memory_recent ON project_memory(conversation_id,created_at DESC);
CREATE TABLE IF NOT EXISTS project_analysis_tasks (
 task_id uuid PRIMARY KEY REFERENCES tasks(id), conversation_id uuid NOT NULL REFERENCES project_conversations(id),
 request_key text NOT NULL, UNIQUE(conversation_id,request_key)
);

ALTER TABLE project_memory ADD COLUMN IF NOT EXISTS concepts text[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS project_memory_concepts ON project_memory USING gin(concepts);
