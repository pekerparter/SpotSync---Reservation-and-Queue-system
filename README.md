# SpotSync

SpotSync is a Django reservation, appointment, and waiting-list application for
customers and business staff. Customers register, browse businesses by category,
view locations, join queues, manage bookings, and update their profiles. Staff
manage business information, service options, weekly hours, queue estimates,
customer booking statuses, and business-scoped roles and permissions.

The application serves HTML and JSON from one Django app. Google Maps is optional.
Read the [security rollout notes](docs/security-hardening.md) before deploying or
handling retained historical data. Phase 3 changes repository maintenance and
verification; it does not change booking rules, routes, models, or migrations.

## Technology and layout

- Python 3.12; Django 5.2.17 LTS.
- PostgreSQL (17 used by CI); psycopg2 2.9.10.
- Django templates, browser JavaScript, Tailwind's CDN, optional Google Maps SDK.
- Pillow for uploaded images and Requests for server-side geocoding.
- Django's test runner, Node's built-in test runner, Ruff 0.14.0, GitHub Actions.

| Path | Purpose |
| --- | --- |
| `SpotSync/manage.py` | Django management entry point |
| `SpotSync/requirements.txt` | Pinned direct runtime dependencies |
| `requirements-dev.txt` | Runtime requirements plus pinned Ruff |
| `SpotSync/SpotSync/` | Settings, root URLs, WSGI/ASGI, opt-in CI settings |
| `SpotSync/accounts/` | Models, booking helpers, permissions, forms, views, admin, tests |
| `SpotSync/accounts/migrations/` | Existing database history; preserve for upgrades |
| `SpotSync/accounts/templates/accounts/` | Customer/staff pages and inline scripts |
| `SpotSync/templates/base.html` | Shared page layout |
| `SpotSync/static/` | Maintained source images and JavaScript; keep these |
| `SpotSync/media/` | Retained historical uploads; new uploads are ignored |
| `SpotSync/*.json`, `SpotSync/db.sqlite3` | Retained historical snapshots; not setup fixtures |
| `tests/` | Dependency-free JavaScript regression tests |
| `.github/workflows/ci.yml` | Pull-request and main-branch validation |
| `docs/` | Audit, security, Phase 3 results, Maps operations, Phase 4 plan |

`venv/` and `SpotSync/staticfiles/` are no longer tracked. Create a fresh virtual
environment; regenerate collected static output when deploying. Existing local
copies may remain after upgrading an older checkout. There is no npm project or
frontend build step.

## Local setup

Install Python 3.12, PostgreSQL, and Node.js 22 (for JavaScript tests). On
Debian/Ubuntu, building the declared `psycopg2` dependency requires a C compiler,
Python development headers, and `libpq-dev`/`pg_config`:

```sh
sudo apt-get install python3.12-venv python3.12-dev build-essential libpq-dev postgresql
```

Python package availability depends on your OS release. Use its supported Python
3.12 installation method if these package names are unavailable.

From the repository root, in a POSIX shell:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
```

For runtime-only installation, use `python -m pip install -r
SpotSync/requirements.txt`. Windows uses `.venv\Scripts\Activate.ps1` in
PowerShell; it may also require PostgreSQL development tools and a compatible C
compiler. The removed Windows environment is not a supported installation method.

### PostgreSQL

Start PostgreSQL using your platform's service manager. As a PostgreSQL
administrator, provision an empty database and an owning role. For example,
using PostgreSQL client tools with administrator authentication:

```sh
createuser --pwprompt --createdb spotsync_user
createdb --owner=spotsync_user spotsync
```

The password prompt keeps the chosen password out of shell history. `CREATEDB`
is needed for Django tests; a production application role should not have that
privilege. Configure PostgreSQL's local password authentication as appropriate.
Do not import the checked-in SQLite database or JSON exports for setup or tests:
they contain historical user/session data and may have old schemas.

### Private environment variables

Settings read the process environment directly. A `.env` file is ignored by Git
but is **not automatically loaded**. Use your shell, IDE, or a private secret
manager to inject values. Never commit keys, passwords, exports, or private
settings.

| Variable | Meaning / default |
| --- | --- |
| `SPOTSYNC_SECRET_KEY` | Private Django signing key; keep stable across workers/restarts |
| `SPOTSYNC_DEBUG` | Defaults to `true`; `true`, `1`, `yes` enable debug, case-insensitively |
| `PGDATABASE` | PostgreSQL database, default `spotsync` |
| `PGUSER` | Role, default `spotsync_user` |
| `PGPASSWORD` | Private database password; default empty, no embedded fallback |
| `PGHOST` | Host/socket directory, default `localhost` |
| `PGPORT` | Port, default `5432` |
| `GOOGLE_MAPS_API_KEY` | Optional private **server** geocoding credential |
| `GOOGLE_MAPS_BROWSER_API_KEY` | Separate optional **browser** credential, referrer/API restricted |
| `DJANGO_SETTINGS_MODULE` | Normally `SpotSync.settings`; supports a private override module |

Set the `PG*` variables for your local database and inject `PGPASSWORD` privately.
For a development session, a new signing key can be generated without displaying
it (the following command requires the activated Python environment):

```sh
export SPOTSYNC_DEBUG=true
export SPOTSYNC_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
export PGDATABASE=spotsync PGUSER=spotsync_user PGHOST=localhost PGPORT=5432
```

This creates a new key each time the command runs. Persist a stable private value
for ongoing sessions. Without a key, development generates an ephemeral key at
process startup, invalidating sessions/reset tokens after restart. With
`SPOTSYNC_DEBUG=false`, a missing signing key prevents startup. Signing-key
rotation invalidates existing signed sessions/reset tokens.

### Start the application

With the environment activated and PostgreSQL/private settings configured:

```sh
cd SpotSync
python manage.py migrate --noinput
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>; the root redirects to `/accounts/login/`. Register a
customer through the UI. Create an admin with `python manage.py createsuperuser`.
Password-reset emails print to the development console; external delivery is not
configured. The application timezone is `Europe/Istanbul`.

Management commands run beside `manage.py`:

| Command | Behavior |
| --- | --- |
| `create_business` | Interactively creates a business and selects categories/options |
| `make_user_business_owner` | Associates an existing account/business and grants owner permissions |
| `create_missing_business_hours` | Adds default weekday hours to businesses with no hours |
| `populate_db` | **Destructive:** deletes categories/businesses and cascades to bookings before creating samples |

Run commands as `python manage.py <command>`. Use `populate_db` only on an
explicitly disposable database. Some sample image names differ in case on Linux.

## Automated verification

Activate the environment and point `PG*` at an empty **disposable development**
database owned by a test role with `CREATEDB`. The tests create and destroy
`test_<PGDATABASE>`; they do not restore snapshots. Use PostgreSQL so all four
row-lock concurrency tests execute (SQLite would skip them).

For uploads/static output isolated from retained files, opt into the CI settings
from the repository root:

```sh
export DJANGO_SETTINGS_MODULE=SpotSync.ci_settings
export SPOTSYNC_CI_OUTPUT_DIR="$(mktemp -d)"
cd SpotSync
python manage.py check --fail-level WARNING
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py migrate --check
python manage.py test --noinput --verbosity 2
python manage.py collectstatic --noinput
```

`ci_settings` requires that temporary output directory and disables both live
Maps bindings. It inherits database configuration from `PG*`; choose the
disposable database **before** running migrations. It is for verification only.
Unset `DJANGO_SETTINGS_MODULE` and `SPOTSYNC_CI_OUTPUT_DIR` before returning to
normal development settings. Retain PostgreSQL's real transaction behavior; do
not replace row locks with mocks.

From the repository root:

```sh
node --test tests/*.test.cjs
ruff check .
ruff check SpotSync/accounts --select I
```

No `npm install` is required. Ruff checks unused/undefined names across maintained
Python code and import ordering in `accounts`; migrations and generated assets
are excluded. This intentionally preserves the existing lint scope without a
formatting refactor. Maps tests use synthetic placeholders and mocked responses.
Coverage includes authentication, business access, staff roles, booking
validation/status changes, queue consistency/concurrency, credential separation,
error-log redaction, and existing route aliases. Browser end-to-end coverage
remains future work.

### GitHub Actions

[CI](.github/workflows/ci.yml) runs on pull requests and pushes to `main`, using
Python 3.12, Node 22, and a disposable PostgreSQL 17 service. It installs the
committed requirements (including source `psycopg2`), checks dependency
compatibility, runs Ruff and JavaScript tests, checks Django/migrations, applies
migrations to an empty service database, runs every discovered Django test,
and verifies static collection. A generated temporary signing key and temporary
media/static directories isolate the job from retained data. No production or
Google Cloud secrets are required, including for fork pull requests.

Failing commands fail the job and show their output in the Actions log. The job
has a 15-minute limit and cancels obsolete runs for the same ref. It does not
deploy or merge. Maintainers can make `validate` a required branch-protection
check after verifying a real run. Local validation is not proof of a remote pass.

## Google Maps

Use `GOOGLE_MAPS_API_KEY` for server-side Geocoding API calls and a different
`GOOGLE_MAPS_BROWSER_API_KEY` for the Maps JavaScript SDK/Places autocomplete.
The browser key is intentionally visible to visitors; it must have website and
API restrictions. The server credential is never used as a browser fallback.

Without a browser key, the SDK is omitted and maps/autocomplete remain inactive;
ordinary pages/forms still render. Without a server key, geocoding is skipped.
Failed geocoding preserves existing/manual coordinates and does not block the
business information save. Transport/JSON failures log a generic message without
request URLs or credential values.

Follow the [Google Cloud operator checklist](docs/google-maps.md) to revoke old
keys, create separate replacements privately, enable the required APIs, restrict
each credential, and configure quotas. Removing literals does not revoke leaked
keys or erase Git history. No historical key should be tested or reused.

## Limitations and deployment

- Development settings allow only `localhost` and `127.0.0.1`. Deploy with a
  private settings module (for example the ignored `SpotSync.local_settings`
  importing `.settings`), explicit hosts/CSRF origins, debug disabled, private
  credentials, and suitable secure-cookie/TLS/HSTS settings.
- Use a production WSGI/ASGI server, HTTPS, external email delivery, backups, and
  a separate media store. `runserver` and the console email backend are for
  development. Serve static assets collected with
  `python manage.py collectstatic --noinput` using deployment settings; do not
  rely on the development static/media handlers in production.
- Run `python manage.py check --deploy` with your real deployment settings. The
  base development configuration still has five deployment warnings; the normal
  CI system check does not certify production readiness.
- Retained snapshots contain sensitive user/session material. Their retention,
  secure archival, and historical credential rotation require owner decisions;
  Phase 3 does not delete data or rewrite Git history.
- The reservation uniqueness constraint includes cancelled non-null options.
  Admin/direct SQL/bulk operations can bypass web/model invariants. These schema
  and data-review issues remain separate, reviewed work.
- Tailwind/Maps depend on external CDNs. Legacy Places autocomplete availability
  depends on Google project eligibility. JavaScript is largely inline; map
  coordinate handling and browser failure states need wider browser coverage.
- Direct dependencies/tools are pinned, but the complete transitive dependency
  graph and PostgreSQL service image digest are not locked. Reproducible installs
  are verified for this phase; future resolution can change transitive packages.

See [Phase 3 results](docs/phase-3-cleanup.md), the original
[cleanup audit](docs/cleanup-plan.md), and the incremental
[Phase 4 refactoring plan](docs/phase-4-refactoring.md).
