# ERPNext operations and access

## Current status
The local ERPNext add-on remains the live installation. This repository does **not yet** provide a functioning backup button or maintenance API. Do not switch installations until a tested backup/restore exists.

## Planned administration interface
A dedicated authenticated **Maintenance** page, not an unauthenticated HTTP command endpoint:
- **Create backup**: run `bench --site frontend backup --with-files`; report result and archive names, and provide a safe way to export the archives.
- **Backup history**: timestamp, file sizes, completion state, retention policy and downloadable archives.
- **Restore**: explicit confirmation, verified archive selection, maintenance mode and rollback guidance. No unattended restore.
- **Status**: installed apps and versions, database/Redis health, background queues, scheduler, last backup, disk space and recent service errors.
- **Logs**: read-only recent service logs with secrets redacted.
- **Access**: show the ERPNext web URL, reverse proxy configuration guidance, login/roles, and safe HTTPS exposure status.

## Security requirements
- Use Home Assistant ingress with authenticated supervisor proxying or an equivalent verified admin authentication layer; do not assume `webui` or a published TCP port is authenticated by Home Assistant.
- Keep the ERPNext application login and permissions enabled.
- Do not expose `bench`, shell commands, restore operations, or backup downloads as public endpoints.
- Keep site encryption keys, passwords and backup files out of source control.
- Add CSRF protection for state-changing browser operations; require explicit confirmation for restore.
- Implement rate limits, timeouts, audit logging, and backup retention limits.

## Before deployment
1. Create a Home Assistant **cold** backup of the local ERPNext add-on and verify that the backup is available.
2. Add and test native Frappe backup/restore in a development copy.
3. Verify the exact installed app set and `site_config.json` encryption key can be restored.
4. Deploy GitHub-hosted ERPNext to a separate add-on data directory and test login and attachments.
5. Switch the reverse proxy only after the restored site is verified.
