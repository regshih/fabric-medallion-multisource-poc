# Security model and review

## Boundaries

- Databricks/Unity Catalog source permissions do not automatically become Fabric permissions. Existing mirroring is preserved; no platform authorization is changed by the app.
- Live Fabric SSO uses the Microsoft auth-provider package. Embedded initialization runs before rendering a session. Standalone sign-in is initiated by a user gesture. Sessions are memory-only (`authStorage: false`). The public portal origin and trusted HTTPS backend are checked; no arbitrary caller-supplied URL or token endpoint is accepted.
- The Warehouse connector explicitly uses **delegated** identity and read-only operations. Do not rely on the SQL connector's application-identity default or assume developer schema discovery proves consumer access.
- Each new detail projection joins the existing RLS-protected risk profile. The app views do not bypass that profile by reading a Lakehouse fact directly. This describes the configured policy; local schema checks alone do not establish runtime enforcement.
- App events are creator-scoped using a generated database predicate. Authenticated users can create/read their own rows; no anonymous, update or delete operation is granted. Client identity guards are convenience checks; the generated database policy is the authorization boundary.
- Routing labels do not grant membership, source privileges or another investigator access. No default admin claim or caller-editable authorization role exists in the app.

## Data handling

All banking and demo records are synthetic. Notes render as React text, never raw HTML. User input lengths, status vocabulary, customer identifier shape and finite numeric values are validated. Date values normalize before event reconstruction. No secret, access token, SQL password or PAT is stored in source. VITE values are public browser configuration; administrative credentials must never appear there.

Demo IndexedDB is isolated by browser origin and is not authentication. It is suitable only for synthetic presentation work. Storage failure is shown explicitly, with no success toast. Append operations use event UUIDs; retrying an already-persisted UUID fails instead of creating a duplicate. Browser data clearing or profile loss removes local records.

Source reads are bounded. Search is over the loaded cohort. Queries use typed SDK filters rather than user-generated SQL/GraphQL fragments. Monetary amounts retain their currency; a mixed-currency source aggregate is not exposed as a USD KPI. Missing quality evidence never becomes PASS. A live failure never triggers fixtures.

## Dependency review

All direct dependencies and the lockfile are pinned. Rayfin SDK/CLI packages are aligned at **1.36.2**, verified from installed package declarations and the registry. Initial dependency auditing reported 19 advisories through the SDK tool chain. The package overrides pin patched `@azure/msal-node` 7.2.2, Zod 4.6.7, glob 14.0.4 and minimatch 11.0.5. Installation then reported **zero vulnerabilities**. See validation for the final audit result.

The overrides intentionally retain the documented Rayfin connector API while updating vulnerable transitive packages. Some overrides cross transitive major versions; local schema generation, CLI help/config parsing, builds and tests must be rerun after upgrades. Azure CLI token authentication, deployment, database/connector apply and the live desktop workflow succeeded after authorized Fabric Apps enablement. Interactive Rayfin login remains unverified. A clean package audit does not establish cloud or application security.

Advisories addressed: [MSAL](https://github.com/advisories/GHSA-xcx6-jx8p-x3h5), [Zod](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5), [glob](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4), [minimatch](https://github.com/advisories/GHSA-g3hv-75wg-m249).

## POC limitations

The event stream is not a tamper-proof compliance audit: timestamps and routing labels originate in the client. Simultaneous status updates resolve by timestamp then UUID, without transaction locking. Owner policies prevent cross-user event access, but do not constitute a team case-management authorization model. There is no automated retention/export policy, supervisory role, notification delivery, production monitoring or disaster-recovery implementation for this app.

Source Warehouse refreshes temporarily replace its existing security-bearing tables in the original repository. This extension does not refactor that behavior. Live source refreshes and permissions need independent operational review; never infer continuous policy enforcement from local schema tests.
