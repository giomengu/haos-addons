# ERPNext local-to-GitHub HAOS add-on migration

## Current installation
- Existing local add-on: `local_erpnext` (slug `erpnext`), version `0.1.11`.
- HAOS persistent data mounted at `/home/frappe/frappe-bench/sites`.
- MariaDB and Redis state are currently under the persisted sites tree.
- GitHub-hosted add-on will have a different full add-on identifier and a separate data directory.

## Recommended procedure
1. Keep the local add-on installed and unchanged. Take a **cold** Home Assistant backup including its data. Verify that the backup completed and can be accessed.
2. While the existing site is operational, generate a **native Frappe site backup** using `bench --site frontend backup --with-files` (verify the site name with `bench list-sites`). Record the exact database backup and public/private file archives. Preserve the original `sites/frontend/site_config.json` securely, especially `encryption_key`. Do not commit backups or credentials to Git.
3. Build the GitHub add-on image and install it separately, initially with its ports unpublished or remapped to avoid conflicts. Do not start two instances against the same database.
4. Create a fresh target site with the same compatible Frappe/ERPNext versions and installed app set. Restore using `bench --site frontend restore <database-backup> --with-public-files <public-archive> --with-private-files <private-archive>`. Supply database credentials as required by the target bench; restore the original site encryption key securely. Ensure the target site's database name and credentials are consistent with its `site_config.json`.
5. Run the appropriate `bench --site frontend migrate` after all required custom apps are installed. Check app versions, site configuration, login, tasks, attachments, background workers, scheduler, custom fields and Server Scripts. Keep the new scheduling hooks disabled until the pilot project passes.
6. Switch the reverse proxy and mapped port only after verification. Keep the original add-on and backup available for rollback; do not uninstall it immediately.

## Cautions
- Native Frappe backup/restore is the data migration path. Home Assistant add-on backups alone do not automatically remap data between `local_erpnext` and a new repository identifier.
- Do not blindly copy the MariaDB data directory between images or database versions.
- Redis queue state generally should not be treated as durable business data.
- This document is a plan, **not evidence that a migration or backup has been executed**.
