-- One database and one login role per service (data ownership rule).
-- Dev-only throwaway passwords; in Azure, services use Entra authentication instead.
CREATE ROLE backstage LOGIN PASSWORD 'dev-only-not-a-secret' CREATEDB;
CREATE ROLE orchestrator LOGIN PASSWORD 'dev-only-not-a-secret';

CREATE DATABASE backstage OWNER backstage;
CREATE DATABASE orchestrator OWNER orchestrator;

REVOKE ALL ON DATABASE backstage FROM PUBLIC;
REVOKE ALL ON DATABASE orchestrator FROM PUBLIC;
