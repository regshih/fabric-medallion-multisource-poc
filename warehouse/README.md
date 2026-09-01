# Gold Warehouse serving contract

Execute the scripts in numeric order after the Gold Lakehouse build:

1. `00_refresh_gold_serving.sql` refreshes three local security-bearing tables and creates zero-copy views for the remaining Gold objects.
2. `10_apply_security.sql` reapplies DDM and native RLS metadata erased by CTAS replacement.
3. `20_validate_security.sql` inventories the configured policy and masks.

`configure_risk_investigator.template.sql` is optional and requires a deploy-time Microsoft Entra principal. No identity is embedded in source control.

The local copies are intentional: DDM and Warehouse RLS cannot be attached to a Lakehouse table through a cross-database view. DDM validation must use a least-privileged Viewer because Fabric workspace Admin, Member, and Contributor roles (and `CONTROL`/`UNMASK`) see unmasked values. RLS does not have that automatic administrator bypass; its policy applies to dbo as well.

