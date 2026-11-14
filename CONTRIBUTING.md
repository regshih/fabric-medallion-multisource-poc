# Contributing

This repository is an independent proof of concept using synthetic banking records. Keep changes focused and preserve the existing Databricks, Cosmos and Fabric platform when extending the app.

## Local setup and checks

Use Python 3.11+ for the platform tooling, and Node.js 24 LTS with npm for `fabric-app/`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/security_scan.py --working-tree --git-history
cd fabric-app
npm ci
npm run check
npm run schema:check
npm run fabric:validate
npm audit --audit-level=high
```

On Linux/macOS, use `.venv/bin/python` instead. Run `npm run dev` for the explicitly labeled local demo. No Azure account is needed for the app's local checks. Cloud deployment is a separate, explicitly authorized operation and can incur charges.

## Pull requests

- Work on a feature branch and describe the problem, resulting behavior and checks performed.
- Include screenshots for visible UI changes, using only synthetic content and no tenant/account context.
- Keep local `.env` files, deployment registries, generated data, logs and notebook outputs out of Git. Use placeholders for all environment identifiers and endpoints.
- Rayfin can append a deployed hosting origin to the tracked `rayfin/rayfin.yml`. Remove that generated environment-specific line before publishing source; the release scanner rejects live Fabric URLs.
- Never include credentials or real customer data in code, fixtures, issues or pull requests. Follow [SECURITY.md](SECURITY.md) for private reporting.
- Keep Rayfin package versions aligned and update the lockfile with dependency changes. Review transitive overrides when upgrading the SDK.
- Identify any cloud validation that was not performed. A local build does not prove a successful deployment.

CI runs checks without cloud credentials or deployment. Maintainers review changes before merging. Contributions are provided under the repository's [MIT license](LICENSE); third-party components retain their own licenses. Communicate respectfully and keep discussions focused on the technical work.
