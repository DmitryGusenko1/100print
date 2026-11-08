-- Issue 23: durable containment for already loaded project processes.
-- Applies only to this project's task tables. No roles/host settings are changed.
CREATE OR REPLACE FUNCTION issue23_deny_agent_dispatch() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (TG_TABLE_NAME = 'tasks' AND NEW.status = 'processing') OR
     (TG_TABLE_NAME = 'hermes_bridge_jobs' AND NEW.status = 'running') THEN
    RAISE EXCEPTION 'issue23: autonomous execution paused pending verified runtime isolation'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS issue23_pause_dispatch ON tasks;
CREATE TRIGGER issue23_pause_dispatch BEFORE INSERT OR UPDATE OF status ON tasks
FOR EACH ROW EXECUTE FUNCTION issue23_deny_agent_dispatch();
DROP TRIGGER IF EXISTS issue23_pause_dispatch ON hermes_bridge_jobs;
CREATE TRIGGER issue23_pause_dispatch BEFORE INSERT OR UPDATE OF status ON hermes_bridge_jobs
FOR EACH ROW EXECUTE FUNCTION issue23_deny_agent_dispatch();
