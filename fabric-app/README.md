# Signal — Fabric Risk Workbench

A React/TypeScript Fabric App POC that turns the existing Databricks + Cosmos → Fabric Gold customer-risk model into an investigation workflow. The original source jobs, notebooks, pipelines, infrastructure and datasets are preserved. Gold remains in **Fabric**.

**Deployed and verified in an approved development environment. Dashboard, drilldown, reconciliation and investigation create/update/note-only saves survived a full reload.** Deploy your own instance using the [deployment guide](docs/DEPLOYMENT.md); environment URLs and identifiers are intentionally private. Mobile and cross-browser acceptance remain pending. The separate local demo contains independently generated, explicitly labeled synthetic records. See [validation evidence](docs/VALIDATION.md).

## Run the local demo

Use Node.js 24 LTS and npm:

```powershell
cd fabric-app
npm ci
npm run dev
```

Open **http://127.0.0.1:5173/**. No cloud account or Docker is required. Windows users can also run `powershell.exe -NoProfile -File scripts/start-demo.ps1` with Node.js and npm on PATH. `npm run dev` starts Vite only; it never provisions a backend.

The default mode is an explicit **Synthetic demo** with 120 customers. Open a customer, inspect signals/transactions/digital activity, select Investigation, enter an assignment label and note, and create the investigation. Updates survive refresh through browser IndexedDB. Use the same origin/browser profile to recover them; private browsing, clearing site data, or changing ports can remove or isolate them. Demo storage is not a protected multiuser service.

## What is implemented

- Responsive overview with cohort-scoped KPIs and a distribution chart.
- Search, risk filtering, sorting and pagination over the loaded cohort.
- Customer drilldowns with the existing Gold formula explained by factor.
- Transaction amounts in their source currencies; no invented FX conversions.
- Investigator-owned cases, routing labels, status changes, notes and an append-only activity trail.
- Separate app-owned persistence: IndexedDB for demo, Rayfin SQL for live mode.
- Fabric SSO and generated creator policies for the live app.
- Read-only delegated Warehouse connector, bounded queries, typed source filters and runtime validation.
- Freshness, run lineage and reconciliation indicators; unavailable evidence is explicit.
- Interactive data journey and a [standalone architecture diagram](docs/architecture.svg).

Assignment is a **routing label**, not access delegation. Live case events are private to their creator. Cross-investigator collaboration, team membership management, email notifications and transactional case locking are outside this POC.

## Verify locally

```powershell
npm run check            # ESLint, TypeScript, production build, component/domain tests
npm run schema:check     # compile models; generate/check real Rayfin DAB configs offline
npm run fabric:validate  # local configuration checks only
npm audit
```

`schema:check` uses the pinned SDK's analyzers, not a hand-written substitute. Generated files stay in ignored `.local/`. Keyless connector notices are intentional: no primary key is fabricated for SQL views. Vite 8 does not lower Stage 3 decorators itself, so a small Vite plugin uses the installed TypeScript compiler for `rayfin/` models. The same models also compile through `tsc` and execute directly in Node during schema checks.

## Live mode and deployment

Follow [deployment instructions](docs/DEPLOYMENT.md). Live mode is selected explicitly with `VITE_DATA_MODE=live` and never falls back to fixtures. Configured live source failures remain visible. The app reads five optional `risk_app` serving views; [their SQL](sql/01_app_serving_views.sql) is additive and must be reviewed/applied only to an approved environment.

The development application workspace and source changes were explicitly approved. Its existing F4 remained **Active (billable)** after verification, and all five additive `risk_app` serving views passed live SQL probes. After administrator authorization, the `AppBackendTenant` setting was enabled through the documented API; deployment then succeeded with the app SQL database, delegated Gold connector and protected static hosting. Status checks and signed-in workflow verification succeeded. See [deployment evidence](docs/LIVE-PREFLIGHT.md). Original source objects and pipeline definitions are preserved.

## Customer handoff

- [Architecture and integration decisions](docs/ARCHITECTURE.md)
- [Fabric deployment and live acceptance](docs/DEPLOYMENT.md)
- [Seven-minute customer walkthrough](docs/DEMO.md)
- [Security model and dependency review](docs/SECURITY.md)
- [Verification results and limitations](docs/VALIDATION.md)
- [Official documentation reviewed](docs/SOURCES.md)

All source banking data and app demo records are synthetic. The risk score is an explainable, uncalibrated heuristic and must not be used for real customer eligibility or fraud decisions.
