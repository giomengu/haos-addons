# ALD Engineering native backup interface

This is the planned Frappe Desk page for a native backup button. The backend implementation is in `ald_engineering/maintenance.py`. It is not operational until the app is installed in the ERPNext image.

## UI
- **Create full backup** (Administrator only): POST `/api/method/ald_engineering.maintenance.create_backup`.
- **Recent backups** (Administrator only): GET `/api/method/ald_engineering.maintenance.list_backups`.
- Display queued job ID and poll its status using authenticated Frappe APIs.
- Show timestamp, file name and size; do not expose arbitrary filesystem paths.

## Required before release
- Create a proper Frappe Desk page under the installed `ald_engineering` app and add the button.
- Verify background worker user, `bench` executable path and job timeout in the HAOS image.
- Verify `bench --site frontend backup --with-files` actually creates database, public and private file archives.
- Implement authenticated archive export (no public static downloads).
- Add backup retention and available-disk-space checks.
- Test restore into a separate site and verify the encryption key is retained.
- Do not enable a web-based restore button before restore is tested end to end.

## Current deployment status
The running local ERPNext add-on has **not** been modified. The backup button is **not available yet**.
