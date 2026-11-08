# ERPNext v0.1.12 — HAOS add-on (experimental)

The GitHub-hosted ERPNext add-on is now published with `config.yaml`, `Dockerfile`, `startup.py`, and `supervisord.conf`. It uses ERPNext v16.53.0, MariaDB, Redis, Frappe workers, Nginx, and optional Frappe Studio.

**Not yet built or smoke-tested.** The current source has been published to allow Home Assistant discovery. Installation may involve a lengthy local Docker build and may expose build errors.

## Parallel installation and safety

- Existing local ERPNext: `local_erpnext`, port **8088**, data remains untouched.
- New repository ERPNext: separate add-on identity, port **8089**, separate persistent data.
- **Do not uninstall or overwrite the local ERPNext add-on.**
- Set a unique strong `admin_password` (minimum 12 characters) in the new add-on configuration before starting it. The default `CHANGE_ME` intentionally prevents startup.
- Do not configure the reverse proxy to point to the new instance until after native Frappe restore and verification.

## Future releases

The ALD Engineering scheduling app and administrator-only native backup button are staged for later releases, **not enabled in v0.1.12**. The files in `ald_engineering/` are development sources only.

See [native migration plan](MIGRATION.md) and [maintenance/access design](OPERATIONS.md).

**No database migration or backup has been performed.**
