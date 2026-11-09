#!/usr/bin/env python3
"""Home Assistant OS single-container ERPNext bootstrap (experimental).

The upstream image already supplies Frappe, ERPNext, its assets, Bench,
Gunicorn, Nginx configuration template and the Node WebSocket server.
This wrapper adds a local MariaDB + two local Redis instances, supervises all
services, and persists the entire site and database in the HAOS 'data' mount.
"""

import json
import os
import pathlib
import pwd
import secrets
import stat
import signal
import socket
import subprocess
import sys
import time

BENCH = pathlib.Path('/home/frappe/frappe-bench')
SITES = BENCH / 'sites'  # HAOS maps its durable app data here
STATE = SITES / '.haos'
MYSQL = STATE / 'mysql'
REDIS_QUEUE = STATE / 'redis-queue'
SOCKET = '/run/mysqld/mysqld.sock'
SUPERVISOR = '/opt/ha-erpnext/supervisord.conf'
SITE = 'frontend'  # Fixed internal site name; any external Host header works.
IMAGE_VERSION = 'v16.53.0'
STUDIO_BUILD_ID = 'studio-v0.1.6'  # Increment when changing the pinned Studio source


def log(message):
    print(f'[ERPNext/HAOS] {message}', flush=True)


def fatal(message):
    log('ERROR: ' + message)
    raise SystemExit(1)


def run(args, *, frappe=False, capture=False):
    if frappe:
        args = ['runuser', '-u', 'frappe', '--', *args]
    # Do not log the argv: bench new-site arguments contain credentials.
    proc = subprocess.run(args, cwd=BENCH, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,
                          check=False)
    if proc.returncode:
        if capture:
            log((proc.stderr or proc.stdout or '').strip()[-1500:])
        fatal(f'Command failed (exit {proc.returncode}): {args[0]}')
    return proc.stdout.strip() if capture else ''


def owner(path, username, mode=None):
    account = pwd.getpwnam(username)
    os.chown(path, account.pw_uid, account.pw_gid)
    if mode is not None:
        os.chmod(path, mode)


def open_service_parent_paths():
    """Allow mysql/redis to traverse Frappe's home to reach HAOS storage.

    The upstream image owns /home/frappe and the bench as user frappe.
    Database processes run as *different* Unix users.  A 0700/0750 home
    stops those users before the final, correctly chowned datadir is reached.
    Add only 'other execute' (traversal), not read/write permissions.
    """
    for directory in (pathlib.Path('/home/frappe'), BENCH, SITES, STATE):
        current = stat.S_IMODE(directory.stat().st_mode)
        if not current & stat.S_IXOTH:
            directory.chmod(current | stat.S_IXOTH)
            log(f'Enabled service traversal: {directory} ({current:04o} -> {current | stat.S_IXOTH:04o})')


def repair_partial_mysql_initialization():
    """Fix partially created data files after an interrupted *first* init.

    Existing initialized databases are intentionally left untouched.
    """
    if (MYSQL / 'mysql').is_dir():
        return
    mysql_user = pwd.getpwnam('mysql')
    for base, directories, files in os.walk(MYSQL):
        for name in [*directories, *files]:
            target = pathlib.Path(base) / name
            if target.is_symlink():
                continue
            os.chown(target, mysql_user.pw_uid, mysql_user.pw_gid)


def check_service_write(user, directory):
    """Test access as the user that will actually run the database."""
    probe = (
        'import os, sys; '
        'p=os.path.join(sys.argv[1], ".haos-permission-check"); '
        'fd=os.open(p, os.O_CREAT|os.O_WRONLY|os.O_EXCL, 0o600); '
        'os.close(fd); os.unlink(p)'
    )
    result = subprocess.run(
        ['runuser', '-u', user, '--', sys.executable, '-c', probe, str(directory)],
        cwd='/', text=True, capture_output=True, check=False
    )
    if result.returncode:
        details = (result.stderr or result.stdout or 'unknown error').strip()
        log(f'PERMISSION CHECK FAILED: user={user} directory={directory}: {details[-1200:]}')
        for parent in [pathlib.Path('/home/frappe'), BENCH, SITES, STATE, directory]:
            st = parent.stat()
            log(f'PATH {parent}: mode={stat.S_IMODE(st.st_mode):04o} uid={st.st_uid} gid={st.st_gid}')
        fatal(f'User {user} cannot write to persistent directory {directory}')
    log(f'Permission check OK: {user} can write to {directory}')


def prepare():
    if not SITES.is_dir():
        fatal('HAOS data mount is absent at ' + str(SITES))
    options_file = SITES / 'options.json'
    if not options_file.is_file():
        fatal('No options.json in the persistent HAOS data mount. Check config.yaml map:type:data.')
    try:
        opts = json.loads(options_file.read_text())
        admin_password = opts['admin_password']
    except (ValueError, KeyError, OSError) as exc:
        fatal('Cannot read admin_password from HAOS options: ' + str(exc))
    if not isinstance(admin_password, str) or len(admin_password) < 12 or admin_password == 'CHANGE_ME':
        fatal('Set a strong admin_password (at least 12 characters) in the Home Assistant app configuration.')
    remove_builder = opts.get('remove_builder', False)
    if not isinstance(remove_builder, bool):
        fatal('remove_builder must be true or false')
    enable_studio = opts.get('enable_studio', False)
    if not isinstance(enable_studio, bool):
        fatal('enable_studio must be true or false')
    developer_mode = opts.get('developer_mode', True)
    if not isinstance(developer_mode, bool):
        fatal('developer_mode must be true or false in Home Assistant app configuration.')

    enable_server_scripts = opts.get('enable_server_scripts', True)
    if not isinstance(enable_server_scripts, bool):
        fatal('enable_server_scripts must be true or false')

    # Never recursively chown sites on a restart: it also contains MariaDB's
    # independently owned database files and Redis's persistent queue files.
    owner(SITES, 'frappe', 0o755)
    STATE.mkdir(exist_ok=True)
    os.chmod(STATE, 0o755)
    MYSQL.mkdir(exist_ok=True)
    REDIS_QUEUE.mkdir(exist_ok=True)
    owner(MYSQL, 'mysql', 0o700)
    owner(REDIS_QUEUE, 'redis', 0o700)

    # /home/frappe may have mode 0700/0750 in the upstream image.  Merely
    # chowning .haos/mysql does not let mysql traverse those parents.
    open_service_parent_paths()
    repair_partial_mysql_initialization()
    check_service_write('mysql', MYSQL)
    check_service_write('redis', REDIS_QUEUE)

    # The inherited Frappe image puts prebuilt frontend assets elsewhere.
    # HAOS mounts an initially empty directory at sites and hides the image
    # build's original sites contents, so restore the mandatory apps manifest.
    apps = sorted(item.name for item in (BENCH / 'apps').iterdir() if item.is_dir())
    (SITES / 'apps.txt').write_text('\n'.join(apps) + '\n')
    owner(SITES / 'apps.txt', 'frappe', 0o644)

    # HAOS mounts a persistent directory over the image's original sites/.
    # That hides Frappe's baked common_site_config.json, and `bench set-config
    # -g` opens the file for reading before writing it.  Restore the missing
    # configuration without overwriting any existing site-wide settings.
    common_config = SITES / 'common_site_config.json'
    if not common_config.exists():
        try:
            fd = os.open(str(common_config), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, 'w') as handle:
                handle.write('{}\n')
            owner(common_config, 'frappe', 0o644)
            log('Created missing Frappe common_site_config.json')
        except FileExistsError:
            pass
    try:
        common_data = json.loads(common_config.read_text())
        if not isinstance(common_data, dict):
            fatal('common_site_config.json must contain a JSON object')
    except (ValueError, OSError) as exc:
        fatal(f'common_site_config.json is invalid or unreadable: {exc}')
    # Confirm the actual `frappe` Unix user (not root) can read and update
    # the configuration; this prevents another boot-time permissions error.
    permission_probe = subprocess.run(
        ['runuser', '-u', 'frappe', '--', sys.executable, '-c',
         'import sys; f=open(sys.argv[1], "r+"); f.close()', str(common_config)],
        cwd='/', text=True, capture_output=True, check=False,
    )
    if permission_probe.returncode:
        fatal('frappe user cannot write common_site_config.json: ' +
              (permission_probe.stderr or '').strip()[-500:])

    baked_assets = BENCH / 'assets'
    site_assets = SITES / 'assets'
    if not baked_assets.is_dir():
        fatal('The upstream ERPNext image does not contain built frontend assets.')
    if site_assets.is_symlink() or site_assets.is_file():
        site_assets.unlink()
    elif site_assets.is_dir():
        # Preserve unexpected user files instead of deleting a directory.
        fatal('sites/assets is a real directory, expected a symlink. Move it aside and restart.')
    site_assets.symlink_to(baked_assets, target_is_directory=True)

    # Ensure Studio's Vite assets are exposed through the Frappe asset path.
    studio_source = BENCH / 'apps' / 'studio' / 'studio' / 'public' / 'frontend'
    studio_target = baked_assets / 'studio' / 'frontend'

    if studio_source.is_dir():
        studio_target.parent.mkdir(parents=True, exist_ok=True)

        if studio_target.is_symlink():
            studio_target.unlink()

        if not studio_target.exists():
            studio_target.symlink_to(
                studio_source, target_is_directory=True
            )
            log(f'Linked Studio frontend assets: {studio_target}')
        elif studio_target.is_dir():
            log(f'Studio frontend asset directory exists: {studio_target}')
        else:
            fatal(f'Unexpected Studio asset path: {studio_target}')

        asset_dir = studio_target / 'assets'
        if asset_dir.is_dir():
            files = list(asset_dir.iterdir())
            log(f'Studio frontend assets found: {len(files)} files')
            for name in ('studio-CESGFeaU.js', 'globals-DSRHcuWX.css'):
                log(f'Studio asset {name}: {"FOUND" if (asset_dir / name).is_file() else "MISSING"}')
        else:
            log(f'WARNING: Studio asset directory missing: {asset_dir}')
    else:
        log(f'WARNING: Studio frontend dist directory missing: {studio_source}')

    pathlib.Path('/run/mysqld').mkdir(exist_ok=True)
    owner('/run/mysqld', 'mysql', 0o755)
    if not (MYSQL / 'mysql').is_dir():
        log('Initializing local MariaDB database (one-time operation)')
        run(['mariadb-install-db', '--user=mysql', f'--datadir={MYSQL}',
             '--skip-test-db'])
    return admin_password, developer_mode, remove_builder, enable_studio, enable_server_scripts


def secret_value():
    secret_file = STATE / 'db_admin_password'
    if not secret_file.is_file():
        value = secrets.token_hex(32)
        fd = os.open(str(secret_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(value + '\n')
    return secret_file.read_text().strip()


def wait_tcp(port, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=2):
                return
        except OSError:
            time.sleep(2)
    fatal(f'Service on localhost:{port} did not start. Review its logs above.')


def supervisor_ctl(*args):
    run(['supervisorctl', '-c', SUPERVISOR, *args])


def configure_database(db_password):
    # Local MariaDB root authenticates through unix_socket. Frappe's own DB
    # administrator is usable over loopback TCP and is never network-exposed.
    sql = (
        "CREATE USER IF NOT EXISTS 'frappe_admin'@'%' "
        f"IDENTIFIED BY '{db_password}'; "
        "ALTER USER 'frappe_admin'@'%' "
        f"IDENTIFIED BY '{db_password}'; "
        "GRANT ALL PRIVILEGES ON *.* TO 'frappe_admin'@'%' WITH GRANT OPTION; "
        "FLUSH PRIVILEGES;"
    )
    run(['mariadb', '--protocol=socket', f'--socket={SOCKET}',
         '-u', 'root', '--execute', sql])


def frappe_bench(*args, capture=False):
    return run(['bench', *args], frappe=True, capture=capture)


def configure_frappe():
    log('Configuring Frappe local MariaDB and Redis endpoints')
    for args in [
        ('set-config', '-g', 'db_host', '127.0.0.1'),
        ('set-config', '-gp', 'db_port', '3306'),
        ('set-config', '-g', 'redis_cache', 'redis://127.0.0.1:6379'),
        ('set-config', '-g', 'redis_queue', 'redis://127.0.0.1:6380'),
        ('set-config', '-g', 'redis_socketio', 'redis://127.0.0.1:6380'),
        ('set-config', '-gp', 'webserver_port', '8000'),
        ('set-config', '-gp', 'socketio_port', '9000'),
    ]:
        frappe_bench(*args)


def ensure_site(admin_password, db_password):
    site_config = SITES / SITE / 'site_config.json'
    was_new = not site_config.exists()
    if was_new:
        log('Creating ERPNext site and installing ERPNext (first boot can be lengthy)')
        frappe_bench('new-site', SITE,
                     '--db-type=mariadb', '--db-host=127.0.0.1',
                     '--db-port=3306', '--no-mariadb-socket',
                     '--db-root-username=frappe_admin',
                     '--db-root-password=' + db_password,
                     '--admin-password=' + admin_password,
                     '--install-app=erpnext')
        # The documented command for selecting the default site is
        # `bench use`, not the undocumented new-site --set-default flag.
        frappe_bench('use', SITE)
        log('ERPNext site created. Username: Administrator')
    else:
        log('Existing ERPNext site found. Preserving credentials and data.')

    marker = STATE / 'erpnext_image_version'
    if not was_new and (not marker.exists() or marker.read_text().strip() != IMAGE_VERSION):
        log('Upstream image version changed: running site migration')
        log('Deferring image migration until app reconciliation; no automatic migration on startup')
    marker.write_text(IMAGE_VERSION + '\n')
    os.chmod(marker, 0o644)




def installed_apps():
    output = frappe_bench('--site', SITE, 'list-apps', capture=True)
    return {line.split()[0] for line in output.splitlines() if line.strip()}


def reconcile_apps(remove_builder, enable_studio):
    """Never delete Builder data or modify the site without explicit opt-in."""
    installed = installed_apps()
    if 'builder' in installed:
        log('Builder is registered on this site.')
        if remove_builder:
            log('Backing up database and files before Builder removal')
            frappe_bench('--site', SITE, 'backup', '--with-files')
            log('Builder uninstall dry run:')
            frappe_bench('--site', SITE, 'uninstall-app', 'builder', '--dry-run')
            # No --force: if uninstall fails, retain data and stop this migration.
            frappe_bench('--site', SITE, 'uninstall-app', 'builder', '--yes')
            installed = installed_apps()
            if 'builder' in installed:
                fatal('Builder still registered after uninstall; stopping before Studio install')
            log('Builder removed from site.')
            frappe_bench('--site', SITE, 'migrate')
        else:
            log('Builder left untouched; set remove_builder=true after reviewing backup and dry-run.')
            if enable_studio:
                fatal('Remove Builder first or disable Studio installation.')
    else:
        log('Builder not registered; nothing to uninstall.')

    if not enable_studio:
        log('Studio installation disabled. Existing ERPNext remains available.')
        return

    if 'studio' not in installed:
        log('Backing up database and files before installing Studio')
        frappe_bench('--site', SITE, 'backup', '--with-files')
        frappe_bench('--site', SITE, 'install-app', 'studio')
        installed = installed_apps()
        if 'studio' not in installed:
            fatal('Studio install did not register the app')
    log('Running site migration for Studio')
    frappe_bench('--site', SITE, 'migrate')
    frappe_bench('--site', SITE, 'clear-cache')
    log('Studio installed and migrated; open /studio')



def configure_developer_mode(enabled):
    """Persist the selected development mode in this site's configuration.

    Frappe supports true/false as typed values via bench set-config.
    This touches site_config.json (persisted by HAOS), not the container image.
    """
    value = 'true' if enabled else 'false'
    log(f'Setting Frappe developer_mode={value} on site {SITE}')
    frappe_bench('--site', SITE, 'set-config', 'developer_mode', value)
    # The documented procedure requires clearing the site's cache after changing it.
    frappe_bench('--site', SITE, 'clear-cache')
    effective = json.loads((SITES / SITE / 'site_config.json').read_text())
    if effective.get('developer_mode') is not enabled:
        fatal('Developer mode was not saved as a JSON boolean in site_config.json')
    log(f'Frappe developer mode {"ENABLED" if enabled else "DISABLED"}')


def configure_server_scripts(enabled):
    value = 'true' if enabled else 'false'
    log(f'Setting server_script_enabled={value} on site {SITE}')
    frappe_bench('--site', SITE, 'set-config', 'server_script_enabled', value)
    frappe_bench('--site', SITE, 'clear-cache')
    effective = json.loads((SITES / SITE / 'site_config.json').read_text())
    if effective.get('server_script_enabled') is not enabled:
        fatal('Server Scripts setting was not saved correctly')


def main():
    log('Starting ERPNext v16 (experimental HAOS package)')
    admin_password, developer_mode, remove_builder, enable_studio, enable_server_scripts = prepare()
    db_password = secret_value()

    os.environ.update({
        'HOME': '/home/frappe',
        'BACKEND': '127.0.0.1:8000',
        'SOCKETIO': '127.0.0.1:9000',
        'NGINX_LISTEN_PORT': '8080',
        'FRAPPE_SITE_NAME_HEADER': SITE,
        'CLIENT_MAX_BODY_SIZE': '100m',
        'PROXY_READ_TIMEOUT': '180',
        'GUNICORN_WORKERS': '2',
        'GUNICORN_THREADS': '2',
        'GUNICORN_TIMEOUT': '180',
        'FRAPPE_REDIS_CACHE': 'redis://127.0.0.1:6379',
        'FRAPPE_REDIS_QUEUE': 'redis://127.0.0.1:6380',
    })

    supervisor = subprocess.Popen(
        ['supervisord', '-n', '-c', SUPERVISOR],
        stdout=sys.stdout, stderr=sys.stderr,
        cwd=BENCH, env=os.environ.copy(),
    )

    def shutdown(signum, _frame):
        log('Stopping ERPNext services')
        if supervisor.poll() is None:
            supervisor.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        log('Waiting for MariaDB and both Redis instances')
        for port in (3306, 6379, 6380):
            wait_tcp(port)
        # Wait for MariaDB to complete initial startup/recovery, not just TCP.
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            result = subprocess.run(['mariadb-admin', '--protocol=socket',
                                     f'--socket={SOCKET}', '-u', 'root', 'ping'],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, check=False)
            if result.returncode == 0:
                break
            time.sleep(2)
        else:
            fatal('MariaDB did not finish initializing')

        configure_database(db_password)
        configure_frappe()
        ensure_site(admin_password, db_password)
        reconcile_apps(remove_builder, enable_studio)
        configure_developer_mode(developer_mode)
        configure_server_scripts(enable_server_scripts)

        log('Starting API, websocket, queues, scheduler and Nginx')
        for service in ('backend', 'websocket', 'queue-short',
                        'queue-long', 'scheduler', 'nginx'):
            supervisor_ctl('start', service)
        log('ERPNext processes started; open http://HOME_ASSISTANT_IP:8088')

        # Remain PID 1 and let supervisord handle restarts and SIGTERM.
        while True:
            code = supervisor.poll()
            if code is not None:
                fatal(f'Service supervisor exited unexpectedly with code {code}')
            time.sleep(5)
    finally:
        if supervisor.poll() is None:
            supervisor.terminate()
            try:
                supervisor.wait(timeout=70)
            except subprocess.TimeoutExpired:
                supervisor.kill()
                supervisor.wait()


if __name__ == '__main__':
    main()