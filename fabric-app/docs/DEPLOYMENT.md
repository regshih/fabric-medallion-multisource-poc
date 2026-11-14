# Fabric deployment and live acceptance

**Deployed on November 13, 2026.** After explicit approval, the existing shared F4 was resumed and five additive serving views passed live SQL probes. The user then added admin permissions and authorized enabling Fabric Apps. The `AppBackendTenant` setting was enabled, and Rayfin deployed the app, SQL service, Gold connector and protected static hosting successfully. Signed-in dashboard, transaction details, seven reconciliation checks and investigation creation, status/assignment updates and note-only saves passed in Edge, including persistence after a full reload. The capacity remains **Active (billable)**. Mobile and cross-browser acceptance remain pending. See [live deployment evidence](LIVE-PREFLIGHT.md).

Open your deployed Fabric App item in its approved workspace. Its hosting endpoint is protected; the development instance returned HTTP 401 without authentication. Keep deployment URLs, workspace/item identifiers and operator logs in ignored local configuration. They are intentionally excluded from this public sample.

## Prerequisites

1. An explicitly approved Fabric application workspace, assigned an active supported capacity. Verify current Fabric Apps Preview availability for its region. Enabling the workload requires the appropriate tenant administrator. Do not resume a shared capacity or change tenant settings without authorization.
2. Contributor/Member/Admin rights to deploy the new app. Consumer users need app Execute permission and the delegated source permissions described below.
3. An approved existing Gold Warehouse with the repository's serving SQL/security already configured. Apply `sql/01_app_serving_views.sql` only after environment approval. It creates/replaces five views in the new `risk_app` schema; it never edits original source objects or the investigator allowlist. Check for an existing `risk_app` schema/name collision before applying.
4. Grant approved source consumers the minimum required SQL SELECT access to the five app views. Do not use workspace Contributor to solve a read permission problem. Existing source security grants are a separate administrative responsibility.
5. Node.js 24 LTS, npm, the locked dependencies, and interactive Rayfin login. No PAT, client secret or new app registration is required by the source code. Never put tokens in VITE variables or Git.

## Local preparation

```powershell
cd fabric-app
npm ci
npm run check
npm run schema:check
npm run fabric:validate
```

`scripts/deploy.ps1` without `-Execute` prints preparation guidance only and makes no cloud calls. Avoid `npx rayfin dev` for this local-only workflow: the documented default can deploy a backend to Fabric. `npm run dev` launches Vite only.

## Configure the source and application

Use process environment variables for the approved IDs. Identifiers are not passwords, but environment-specific values are deliberately not tracked.

```powershell
$env:GOLD_WORKSPACE_ID = '<existing-approved-source-workspace-id>'
$env:GOLD_WAREHOUSE_ID = '<existing-gold-wh-item-id>'
$env:VITE_FABRIC_WORKSPACE_ID = '<approved-app-workspace-id>'
$env:VITE_DATA_MODE = 'live'
$env:VITE_COHORT_LIMIT = '200'
$env:RAYFIN_TELEMETRY_OPTOUT = '1'
npx rayfin login
```

For local frontend access to an **already deployed** app, copy `.env.example` to ignored `.env.local`, set live mode and the backend URL/publishable key/workspace/app item IDs. The publishable key is public client configuration, not an administrative secret. The CLI's `RAYFIN_PUBLIC_*` values map to the same Vite aliases; `npx rayfin env --framework vite` regenerates deployment frontend configuration. Live URLs must be HTTPS; this POC accepts the public Fabric portal origin only.

Connector identity is explicitly `delegated` in `rayfin/rayfin.yml`; CLI 1.36.2 otherwise defaults SQL connectors to application identity. Do not remove that setting. App users still need their own source permissions. SDK 1.36.2 does not support the newer `connector add --auth` flag; the YAML setting is intentional.

The serving entities are hand-authored against the inspected repository schema and checked using SDK generation locally. After approved views exist, inspect their actual SQL columns and run Rayfin schema discovery before live acceptance. For a fresh connector setup the documented command is:

```powershell
npx rayfin connector search --workspace-id $env:GOLD_WORKSPACE_ID --type fabric-warehouse --json
```

The supplied read-only source probe checks view columns and attempts one permitted row per view without printing record values. Run it with the repository Python environment and Azure CLI on PATH, only when the approved source capacity is active:

```powershell
..\.venv\Scripts\python.exe scripts/probe-source.py --server '<warehouse-sql-host>' --database '<gold-wh-database-name>'
```

An empty permitted result can be valid under RLS; probe success is not an RLS enforcement test.

Do not re-run `connector add --yes` over the supplied `gold` folder: it may overwrite the curated definitions. If discovery differs, reconcile the types and projection SQL; do not claim compatibility based only on successful app creation.

## Deploy only after approval

```powershell
node scripts/validate-config.mjs --live
# Optional read-only CLI preflight; resolves the target but does not deploy:
npx rayfin up --dry-run --workspace-id $env:VITE_FABRIC_WORKSPACE_ID

# Only for an explicitly approved environment:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/deploy.ps1 -Execute
```

The explicit execution creates a new Rayfin app and its application SQL service and can consume capacity. It does not run the optional source SQL, enable a tenant setting, start source pipelines, grant permissions, create a capacity or resume one. Do not pass destructive schema-force flags. The app's auth, data, connector and static hosting declarations are enabled; static assets use `protected` access. The CLI supplies deployment public values before its final frontend build. Keep `.env`, `.deployments.json`, `.temp` and local generated state untracked.

For frontend-only changes after deployment, use `npx rayfin up staticapp deploy --json` with the same approved source identifiers and `VITE_DATA_MODE=live` in the process environment. Even this subcommand resolves connector environment variables from the YAML. Verify the active deployment registry points to the intended existing app before running it. The November 13 Date-normalization fix used this path and did not recreate the database or apply source SQL again.

## Required live acceptance

- Confirm CLI deployment status and the actual hosted URL. An exited CLI or a created app alone is insufficient.
- Sign in as a consumer through Fabric SSO; test standalone and embedded modes as applicable. Close the session and verify protected API access is denied.
- Compare retrieved source schemas and risk/profile values with approved SQL queries. Verify profile, transaction, session and alert filtering for a known customer.
- Save a status, assignment and note; reload and verify persistence in the app database. Verify failed writes do not display success.
- Validate the cohort limit, exact customer reopening, quality run matching, freshness timestamps and explicit live error behavior. Revoke or deny the connector temporarily in a controlled test and confirm no fixtures appear.
- Review the current pinned security overrides and re-run `npm audit`. Preview/SDK upgrades need fresh tests, including CLI login and deployed source identity.
- Complete mobile/cross-browser acceptance. The deployed desktop overview, explorer and customer drawer were inspected in Edge. An earlier URL-policy/browser-access blocker was resolved; it does not describe the final desktop verification result.

## Rollback

The source platform and original pipelines are unchanged. To withdraw the POC, remove app sharing through approved administration and retain/export investigation records according to the agreed retention policy. Do not delete source datasets or capacities. Removing the new app or optional views is a separate reviewed action; no destructive cleanup command is bundled.
