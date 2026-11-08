# ERPNext / ALD Engineering (staging)

This directory is reserved for the existing HAOS ERPNext add-on (currently local slug `erpnext`, version `0.1.11`). The add-on is **not yet published here**. Do not install a second ERPNext instance until a native Frappe backup and a verified restore procedure are ready.

Target layout: `config.yaml`, `Dockerfile`, `startup.py`, `supervisord.conf`, optional Studio/Kanban assets, and `ald_engineering/`.

Keep database and Frappe site data out of Git. Do not commit `site_config.json`, database dumps, backup archives, passwords or encryption keys.

See [MIGRATION.md](MIGRATION.md) for the staged migration plan.
