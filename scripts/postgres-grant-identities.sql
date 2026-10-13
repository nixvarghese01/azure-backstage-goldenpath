-- Run once as the server's Entra administrator (the platform identity), connected to database "postgres".
-- Maps each platform service's workload identity to a PostgreSQL role and grants it ONLY its own database.
-- Replace the names if your environment differs. No passwords are involved.

SELECT * FROM pgaadauth_create_principal('id-idp-backstage-dev', false, false);
SELECT * FROM pgaadauth_create_principal('id-idp-orchestrator-dev', false, false);

GRANT ALL PRIVILEGES ON DATABASE backstage TO "id-idp-backstage-dev";
GRANT ALL PRIVILEGES ON DATABASE orchestrator TO "id-idp-orchestrator-dev";
REVOKE ALL ON DATABASE backstage FROM PUBLIC;
REVOKE ALL ON DATABASE orchestrator FROM PUBLIC;

-- Backstage creates per-plugin databases when allowed; with a single database it uses schemas instead
-- (backend.database.pluginDivisionMode: schema in app-config.production.yaml).
\connect backstage
GRANT ALL ON SCHEMA public TO "id-idp-backstage-dev";
\connect orchestrator
GRANT ALL ON SCHEMA public TO "id-idp-orchestrator-dev";
