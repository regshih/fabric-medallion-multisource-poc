# Deployment and live verification evidence

Verification date: **November 13, 2026**. Results below were observed in an approved development environment. Tenant, subscription, resource, workspace and item identifiers, hosting endpoints and operator logs are deliberately excluded from this public repository.

## Deployment outcome

The existing paused F4 capacity was resumed after explicit approval. Five additive `risk_app` serving views were applied to the existing Gold Warehouse after a name-collision check. All five source probes passed. No original source objects or pipeline definitions were changed, and no source pipeline was run.

The first application creation attempt failed because Fabric Apps was disabled. After the administrator authorized enabling the workload, the tenant setting was updated and read back successfully. Other tenant settings were preserved. This was an environment-specific administrative action; the repository's deployment script does not enable workloads or resume capacity.

Rayfin deployed the app, app-owned SQL database, delegated read-only Gold connector and protected static hosting successfully. Deployment status reported an authenticated management endpoint with HTTP 200. Unauthenticated static hosting returned HTTP 401. The approved existing capacity remained **Active (billable)**; no new capacity or trial was created.

To open your deployment, select its Fabric App item in your approved workspace. Obtain your environment's URLs and item IDs from its deployment output, and keep them in ignored local configuration.

## Signed-in Edge verification

- The live overview and explorer loaded a **200-customer bounded cohort** and **167 source fraud signals**. Counts describe the signed-in user's loaded cohort, not the entire portfolio.
- Desktop layout, navigation and the customer signal drawer were inspected visually. Freshness correctly flagged the September source load as older than 24 hours.
- Reconciliation reported **7/7 checks pass, same run**. A synthetic customer displayed **five retrieved transactions**, with source currencies retained.
- Runtime verification found that the SDK converts date-looking SQL strings to JavaScript `Date` objects. The adapter now normalizes valid Dates to ISO strings and rejects invalid Date objects. Lint, build and all **28 app tests** passed before the corrected frontend was redeployed.
- An investigation was created with a clearly synthetic note. A subsequent update changed status to **Investigating** and assignment to **Validation follow-up**. A separate **Add note only** action appended another note without changing those fields.
- After a full page reload, the queue and reopened activity trail retained the updated fields and all **three activity entries**. No event was deleted and no business action was taken.

## Remaining boundaries

Mobile and cross-browser acceptance remain pending. Embedded mobile emulation scaled the Fabric portal's desktop layout, so it did not establish the standalone app's mobile behavior. Browser automation stopped while opening the standalone view because it could not reliably determine the current URL.

Interactive Rayfin CLI login remains untested: deployment used the installed CLI's supported external-token environment variable with an Azure CLI token. Tokens stayed in process memory and were removed afterward. Avoid upstream CLI verbose logging, which can expose token/header prefixes.

The original September platform results are historical evidence; they were not rerun as part of application verification. Production collaboration, concurrency, retention, monitoring, recovery and performance requirements remain separate from this POC.

## Deployment lessons

- Target an approved existing workspace with `--workspace-id`; CLI 1.36.2 rejects combining it with `--capacity-id`.
- A successful dry run does not prove workload availability or live application behavior.
- Do not reapply source SQL or recreate the app database for a frontend-only correction.
- Generated deployment registries, `.env` files and runtime logs are local operator artifacts, not public source.

Sources: [Fabric Apps overview](https://learn.microsoft.com/en-us/fabric/apps/overview), [deployment](https://learn.microsoft.com/en-us/fabric/apps/deploy-app), [regional availability](https://learn.microsoft.com/en-us/fabric/admin/region-availability), [tenant setting update API](https://learn.microsoft.com/en-us/rest/api/fabric/admin/tenants/update-tenant-setting).
