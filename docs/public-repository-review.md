# Public repository review

Reviewed November 13, 2026, for the Signal Fabric App pull request.

## Changes made

- Added the maintainer-selected MIT license, contribution guidance and a pull request template. Third-party dependencies retain their respective licenses; the README identifies this as an independent sample.
- Removed live tenant/workspace/item IDs, hosting origins and operator diagnostics from the publication copy. Local deployment-history commits were not imported into the publication branch. Public evidence records outcomes and limitations without exposing environment inventory.
- Kept `.env` files, generated deployment registries, local tooling, node modules, build artifacts and logs ignored. Removed a machine-specific Node discovery path from the demo launcher.
- Extended the release scanner to reject live Azure resource paths, Fabric entry-point/hosting URLs and tenant sign-in names. Findings report paths and rule names, never matching values.
- Pinned GitHub Actions to full commit SHAs, retained read-only workflow permissions, disabled checkout credential persistence and bounded job runtime. CI has no cloud credentials, source SQL execution or deployment steps.
- Added weekly Dependabot updates for npm, Python and GitHub Actions, including a group for aligned Rayfin package updates.
- Enabled and read back GitHub secret scanning, push protection, Dependabot security updates and private vulnerability reporting. The security policy links to the private reporting channel.

## Verification

- Fresh app dependency installation, ESLint, TypeScript, production build and **28 app tests** passed.
- Real Rayfin schema generation and local configuration validation passed; five keyless views are intentional.
- **50 Python tests** passed, including two new inventory scanner regression tests.
- The repository release scanner passed against the publication working tree and its Git history. Gitleaks found no secrets in the publication source or history. These are point-in-time checks, not a guarantee that every possible secret is detectable.
- Local Markdown links resolved, tracked notebooks contained no outputs, and generated/local deployment paths were confirmed ignored.
- Dependency audit and placeholder live build are checked by CI. Refer to the pull request checks for the remote result.

The application review retained memory-only live sessions, Fabric SSO, a delegated read-only source connector, generated creator policies, bounded typed queries and explicit failure handling without a synthetic fallback. Public documentation keeps the POC's operational and browser-validation limitations visible.

## Maintainer decisions

The default branch is currently unprotected. Consider requiring pull requests and successful CI once that policy has been reconciled with the existing Fabric Git synchronization workflow. This review does not silently change that workflow or merge the application pull request.

License and new policy/workflow files take effect on the default branch after the pull request is merged. Repository security settings were enabled separately and are already active. No cloud redeployment was performed for this review.

References: [GitHub repository best practices](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories), [secure use of GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use), [Dependabot configuration](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).
