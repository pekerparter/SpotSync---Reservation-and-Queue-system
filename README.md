# SpotSync

SpotSync is a Django application for business waiting lists, reservations, and
appointments. Customers can register, browse businesses, join queues, manage
bookings, and update their profiles. Business staff can manage services, hours,
staff roles, permissions, and customer bookings.

This repository defaults to local development settings. Read the
[security changes and rollout requirements](docs/security-hardening.md) and
[cleanup plan](docs/cleanup-plan.md) before deploying it or loading historical
database exports.

## Structure

| Path | Purpose |
| --- | --- |
| `SpotSync/manage.py` | Django management entry point |
| `SpotSync/SpotSync/` | Settings, root URLs, WSGI and ASGI entry points |
| `SpotSync/accounts/` | Models, forms, authentication, views, routes, admin, and tests |
| `SpotSync/accounts/migrations/` | Database migration history; retain it for existing installations |
| `SpotSync/accounts/templates/accounts/` | Customer and business pages with inline JavaScript |
| `SpotSync/templates/base.html` | Shared layout; Tailwind is loaded from its CDN |
| `SpotSync/static/` | Source static assets |
| `SpotSync/media/` | Historical uploaded images |
| `SpotSync/staticfiles/` | Generated static assets, currently tracked |
| `venv/` | Historical Windows environment; create your own environment instead |

There is one Django app and one PostgreSQL database. Django serves HTML and JSON
endpoints; there is no separate frontend build. Google Maps JavaScript and
server-side geocoding are optional integrations. Development password-reset
emails use Django's console email backend.

## Local development

Use Python 3.12 (validated), PostgreSQL (17 validated), and a fresh virtual
environment. Linux installations of `psycopg2` need a compiler, Python headers,
and PostgreSQL development headers/tools (`pg_config`, commonly from
`libpq-dev`). Never activate the committed Windows `venv/` on Linux.

From the repository root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r SpotSync/requirements.txt
```

If compiling `psycopg2` is unavailable, the same-version `psycopg2-binary==2.9.10`
is a development alternative. Use a separate local requirements copy with that
single substitution; keep the committed requirements unchanged. The prepared
cloud environment uses this alternative.

### Database and private settings

Provision an empty PostgreSQL database and a role that owns it. The role also
needs `CREATEDB` to run Django's tests, which create a separate test database.
Do not restore the checked-in SQLite database or JSON exports automatically:
they are historical snapshots with user/session data and may have old schemas.

The default database name is `spotsync`, with role `spotsync_user` at
`localhost:5432`. Settings now read `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`,
and `PGPORT`. Supply the password through your private process environment;
there is no hardcoded password fallback. An empty password works only where the
local PostgreSQL authentication policy permits it.

Set `SPOTSYNC_SECRET_KEY` privately to a cryptographically random Django signing
key. Keep it stable across server processes and restarts. In development only,
an unset key produces an ephemeral random key, so sessions/reset tokens will
not survive a process restart. `SPOTSYNC_DEBUG=false` requires an explicit key.
The prepared cloud setup retains a private development key outside the checkout;
see its saved startup instructions. No key value belongs in Git or this README.
Existing ignored `SpotSync/SpotSync/local_settings.py` overrides remain supported
through `DJANGO_SETTINGS_MODULE=SpotSync.local_settings`.

With credentials supplied privately, run from the repository root:

```sh
cd SpotSync
python manage.py migrate --noinput
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

The root path redirects to `/accounts/login/`. Register a customer through the
registration page; use `python manage.py createsuperuser` for Django admin.
There is no shared sample-account password.

### Optional sample businesses and ownership

These commands run from the directory containing `manage.py`:

| Command | Behavior |
| --- | --- |
| `python manage.py create_business` | Interactively creates a business and selects categories/options |
| `python manage.py make_user_business_owner` | Interactively associates an existing user/business and grants owner permissions |
| `python manage.py create_missing_business_hours` | Adds weekday default hours only to businesses with no hours |
| `python manage.py populate_db` | **Destructive:** deletes all categories and businesses, cascading to their bookings, before adding samples |

Use `populate_db` only on a disposable development database. Uploaded sample
images come from the source static assets; some legacy names differ in case on
Linux and may not resolve.

### Checks

From `SpotSync/` with your environment activated and database running:

```sh
python manage.py test accounts --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
```

The tests cover accounts, business-scoped authorization, role escalation,
booking validation/concurrency, queue consistency, private configuration, staff
page rendering, and existing route aliases. PostgreSQL concurrency tests use
independent database connections; SQLite skips tests that require row locks. They run against a
temporary database and do not load historical snapshots or call Google APIs.
They do not establish that every authorization path or browser interaction is
secure. `python manage.py check --deploy` currently reports deployment warnings;
production settings and security fixes remain separate work.

Run the small browser escaping regression suite from the repository root with
Node 18 or later (no npm installation is needed):

```sh
node --test tests/security.test.cjs
```

There was no existing linter or CI configuration. For the cleanup's targeted
Python check, optionally run Ruff 0.14.0 from the repository root:

```sh
ruff check SpotSync/accounts --select F,I
```

For deployment, `python manage.py collectstatic --noinput` regenerates
`SpotSync/staticfiles/`; it is unnecessary for Django's development server.

## Google Maps and deployment limitations

Set `GOOGLE_MAPS_API_KEY` privately for server-side geocoding, and configure a
separate `GOOGLE_MAPS_BROWSER_API_KEY` for the browser SDK. Browser keys are
visible to visitors by design: restrict them to the appropriate HTTP referrers
and Maps APIs. The server key is never used as a browser fallback. Without a
browser key, the SDK is omitted; without a server key, geocoding is skipped and
existing/manual coordinates remain available. Geocoding failure does not block
business information updates. Live key validity and restrictions were not tested.

The former embedded keys were removed from current application configuration
and templates. Their copies in Git history and historical session/user exports
remain sensitive: operators must rotate/restrict credentials and review retention.
Do not put replacement keys, passwords, database dumps, or private `.env` files
in Git. Development defaults are not a production deployment configuration.
See [the security rollout notes](docs/security-hardening.md).
