-- Application-role migration: never installs extensions or changes cluster privileges.
CREATE TABLE IF NOT EXISTS project_artifacts (
 id uuid PRIMARY KEY, project_id text NOT NULL DEFAULT '100print' CHECK(project_id='100print'),
 artifact_type text NOT NULL CHECK(artifact_type IN ('decision','hypothesis','task','follow_up','question','risk','user_preference','business_fact','business_model','portal_hypothesis','mvp_scope','customer_journey','unit_economics','production_threshold','growth_stage','metric','experiment')),
 title text NOT NULL, body jsonb NOT NULL DEFAULT '{}', status text NOT NULL DEFAULT 'open',
 owner text NOT NULL DEFAULT 'chief-of-staff', deadline timestamptz, review_at timestamptz,
 importance real NOT NULL DEFAULT .5 CHECK(importance BETWEEN 0 AND 1),
 confidence real NOT NULL DEFAULT .3 CHECK(confidence BETWEEN 0 AND 1),
 provenance jsonb NOT NULL DEFAULT '{}', summary text NOT NULL DEFAULT '',
 entities text[] NOT NULL DEFAULT '{}', topics text[] NOT NULL DEFAULT '{}',
 dedupe_key text NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS artifact_links (
 source uuid REFERENCES project_artifacts(id), target uuid REFERENCES project_artifacts(id),
 relation text CHECK(relation IN ('supersedes','depends_on','contradicts','follow_up','related')),
 PRIMARY KEY(source,target,relation), CHECK(source<>target)
);
CREATE TABLE IF NOT EXISTS artifact_history (
 id bigserial PRIMARY KEY, artifact_id uuid REFERENCES project_artifacts(id),
 event_key text NOT NULL UNIQUE, body jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS project_events (
 event_key text PRIMARY KEY, artifact_id uuid REFERENCES project_artifacts(id),
 kind text NOT NULL, body jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS artifacts_due ON project_artifacts(review_at,deadline) WHERE status NOT IN ('closed','done','rejected','validated');
CREATE TABLE IF NOT EXISTS retrieval_observations (
 id bigserial PRIMARY KEY, provider text NOT NULL, hits integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
-- Embeddings stay usable without pgvector; optional vector index is enabled separately.
CREATE TABLE IF NOT EXISTS memory_embeddings (
 memory_id uuid REFERENCES project_memory(id) ON DELETE CASCADE, model text NOT NULL,
 embedding real[] NOT NULL, PRIMARY KEY(memory_id,model)
);
ALTER TABLE project_memory ADD COLUMN IF NOT EXISTS artifact_type text;
ALTER TABLE project_memory ADD COLUMN IF NOT EXISTS provenance jsonb NOT NULL DEFAULT '{}';
ALTER TABLE project_memory ADD COLUMN IF NOT EXISTS summary text NOT NULL DEFAULT '';
ALTER TABLE project_memory ADD COLUMN IF NOT EXISTS entities text[] NOT NULL DEFAULT '{}';
ALTER TABLE project_memory ADD COLUMN IF NOT EXISTS topics text[] NOT NULL DEFAULT '{}';
CREATE TABLE IF NOT EXISTS memory_links (
 source uuid REFERENCES project_memory(id), target uuid REFERENCES project_memory(id),
 relation text NOT NULL CHECK(relation IN ('supersedes','depends_on','contradicts','related')),
 PRIMARY KEY(source,target,relation), CHECK(source<>target)
);
CREATE TABLE IF NOT EXISTS notification_digests (
 chat_id text NOT NULL, user_id text NOT NULL, day date NOT NULL DEFAULT current_date,
 update_id bigint NOT NULL, PRIMARY KEY(chat_id,user_id,day)
);
