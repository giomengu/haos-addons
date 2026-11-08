# Alpha Lyrae Design — Home Assistant Add-ons

Home Assistant add-on repository for AlphaNav Weather and the upcoming ERPNext / ALD Engineering app.

## Install
In Home Assistant, open **Settings → Apps → Install app → ⋮ → Repositories** and add:

`https://github.com/giomengu/haos-addons`

## Add-ons
- **AlphaNav Weather** — existing weather add-on, still in its original folder; a clean reinstall is acceptable.
- **ERPNext / ALD Engineering** — [staging and migration instructions](erpnext/README.md). **Not yet installable from this repository.** The running local ERPNext add-on and its data are untouched.

## Security and access
- Keep ERPNext's own login and role permissions; Home Assistant ingress is not a substitute for ERPNext authentication.
- Do not publish the ERPNext port directly to the Internet. Use an authenticated HTTPS reverse proxy.
- Store database dumps, site encryption keys, passwords and access tokens outside Git.
- Preserve the existing ERPNext data using both a cold HAOS backup and a native Frappe backup before installing a new add-on identity.

## Operations
See [ERPNext migration](erpnext/MIGRATION.md) and [backup and access plan](erpnext/OPERATIONS.md).

The repository rename does not migrate the installed local ERPNext add-on's data.
