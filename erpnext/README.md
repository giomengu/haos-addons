# ERPNext / ALD Engineering — staging

The running Home Assistant installation is currently the **local** add-on `local_erpnext` (slug `erpnext`, version `0.1.11`).

**Do not install a second ERPNext add-on yet.** The new GitHub-hosted add-on will have a different full identifier and a separate data directory. This folder is staging documentation; it is not an installable add-on until its verified `config.yaml`, Dockerfile, startup scripts, and custom app have been published and tested.

- [Native backup/restore migration](MIGRATION.md)
- [Maintenance, access and security requirements](OPERATIONS.md)

The desired ALD Engineering application will host the relative scheduling engine. Keep it disabled for production projects until the pilot tests pass.

Never commit database dumps, passwords, site configuration with secrets or encryption keys.
