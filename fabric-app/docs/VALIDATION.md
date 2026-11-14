# Validation and remaining prerequisites

Runtime verification date: **November 13, 2026**. The app is an additive folder in the existing repository. Results below describe local checks and one approved development deployment; publishing this source does not deploy it into a reader's environment. Deployment inventory and operator logs are intentionally excluded.

## Executed checks

| Check | Result | Boundary |
|---|---|---|
| Node.js 24.22.3 installation | PASS | Portable official Windows archive verified against the published SHA-256 manifest. |
| Dependency installation and lockfile | PASS | Exact versions pinned. Public npm tarball URLs retain original integrity hashes; no organization-specific feed URL is required by the committed lockfile. |
| ESLint | PASS | Application, model, script and test source. |
| TypeScript | PASS | Frontend, live adapter, Rayfin models and tests. |
| Demo production build | PASS | Explicit fixture/default-demo build. |
| Live production build | PASS | Public placeholder deployment values; generated JS also checked with `node --check`. No backend calls. |
| App automated tests | **28 PASS** | Component interactions, domain semantics, persistence, SDK configuration, mocked connector behavior and live-discovered Date-object regression coverage. |
| Real SDK schema generation | PASS | `tsc` output executed in Node; SDK generates event DAB policy and five read-only keyless connector entities. |
| Local configuration posture | PASS | Auth enabled, Fabric SSO, password disabled, protected assets, read-only delegated source. |
| Installed SDK connector configuration validation | PASS | Supplied connector declaration passes the pinned package validator. |
| Dependency audit | **0 vulnerabilities** | Successful standalone audit after patched overrides. Some earlier repeats were rate-limited; these were not reported as successful. |
| Repository Python tests | **50 PASS** | Original source tests plus two public-inventory scanner regression tests. No notebook/pipeline/infra behavior changed. |
| Repository working tree/history credential scan | PASS | Heuristic scan, not a guarantee that all possible sensitive data is absent. |
| Source-probe script | **5 live probes PASS** | Approved `risk_app` views exist with expected columns; each query returned a permitted sample row without printing its values. The probe does not assess security enforcement. |
| Deployed investigation workflow | **PASS** | Create/read, status and assignment update, and note-only save. A full page reload retained all three activity entries and the updated state. |
| Deployment wrapper default mode | PASS | Prints local-only preparation guidance; no cloud call. |
| Local HTTP preview | **200 OK** | Confirms the Vite app serves; does not establish visual quality or browser compatibility. Preview process stopped after verification. |

The GitHub Actions workflow runs local checks/audit and a placeholder live build, with no cloud credentials or deployment. Its remote results are available on the pull request; local results below do not imply a successful remote run.

## Automated behavior covered

- Schema-valid deterministic fixture generation and coverage of Low/Medium/High bands.
- Score factor explanation agrees with the existing Gold heuristic; currencies are retained.
- Invalid/infinite source values rejected; missing/future freshness is Unknown.
- Case reconstruction, note-only changes, status/assignment persistence and mismatched event rejection.
- IndexedDB persistence across repository instances, duplicate-write rejection and owner checks.
- Customer search/filtering, record opening, case creation, assignment/status save, refresh and failed-write error display.
- Source permission/query failures remain visible; no synthetic fallback in live mode.
- Bounded live cohorts, unavailable quality evidence, exact customer lookup, event pagination and date normalization.
- Quality results from another run are flagged Review rather than passing the loaded cohort.
- Generated creator predicates and absence of anonymous, event-update/delete or Gold-mutation privileges.

## Cloud preflight and approved deployment attempt

The initial read-only preflight found the shared F4 paused. After explicit user approval, Azure ARM resumed the existing F4 in West US 3, and both ARM and Fabric reported it Active. The existing CLI identity had workspace Admin access. Gold Warehouse metadata and SQL access then succeeded. No source pipeline was run.

No existing `risk_app` objects were found before applying `sql/01_app_serving_views.sql`. Its seven batches created the schema and five additive views. Live metadata inspection confirmed their expected columns and SQL types; all five read probes returned permitted rows. No original source objects or permissions were changed. Lint, build, all 25 app tests and SDK schema generation were rerun successfully before deployment.

The first app creation attempt failed with `403 Forbidden: The feature is not available`. After the user added admin permissions, the same Azure CLI session could read tenant settings and confirmed `AppBackendTenant` was disabled. The user explicitly authorized enabling it. The documented update API enabled the setting while retaining its existing delegation configuration and organization-wide scope; a new read verified the result. Other tenant settings and source permissions were unchanged.

Rayfin then deployed the app, workflow SQL database, delegated Gold connector and protected static hosting successfully. The subsequent status check reports `deployed: true` and an authenticated, reachable management endpoint (HTTP 200). An unauthenticated hosting request returned HTTP 401. No additional capacity, trial, workspace assignment, Entra app registration or credential persistence was introduced. The approved existing F4 remains **Active (billable)**. See [detailed evidence and app link](LIVE-PREFLIGHT.md).

Signed-in browser verification reached the live overview and explorer with a 200-customer Gold cohort and 167 source fraud signals. The desktop layout and customer signal drawer were inspected visually. Runtime verification exposed SDK conversion of date-looking SQL values to `Date` objects, causing detail validation and reconciliation parsing failures. The adapter now normalizes valid Dates to ISO strings while rejecting invalid Date objects. Regression tests cover both string and Date representations for transactions, sessions, alerts and quality checks. Lint, build and all 28 tests passed before redeployment. Final post-fix browser acceptance is recorded in the live evidence document.

The repository's September baseline/incremental results remain historical evidence. They are not presented as newly rerun cloud validation. Application fixtures are independently generated and labeled; their 120-row cohort does not reproduce the full 50,000-customer deployed dataset.

## Remaining acceptance

Post-fix transaction details, reconciliation, investigation creation, status/assignment updates and note-only saves **passed**, including a full reload; see [the evidence record](LIVE-PREFLIGHT.md).

1. Complete mobile and cross-browser acceptance. The live desktop overview, explorer and signal drawer were inspected in Edge; this does not establish mobile compatibility. Embedded mobile emulation scaled the Fabric portal's desktop layout, so it did not establish the standalone app's mobile behavior. Browser automation then stopped because it could not reliably determine the current URL when opening the standalone view.
2. Interactive Rayfin login remains untested; the deployment used an Azure CLI token through the SDK's supported external-token environment variable.
3. Review production collaboration, concurrency, tamper-proof audit, retention, monitoring and performance requirements before expanding this POC.

The deploy guide contains a concrete acceptance checklist and a read-only source schema probe. Local schema/build success is not a substitute for these live checks.
