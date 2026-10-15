# SpotSync

SpotSync is a Django application for business waiting lists, reservations, and
appointments. Customers can register, browse businesses, join queues, manage
bookings, and update their profiles. Business staff can manage services, hours,
staff roles, permissions, and customer bookings.

This repository currently has development settings and known security issues.
Read [the audit and cleanup plan](docs/cleanup-plan.md) before deploying it or
loading historical database exports.

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

The default settings use a local database named `spotsync` and role
`spotsync_user`. They contain legacy development credentials and do **not** read
standard PostgreSQL environment variables. To supply private local credentials
without editing tracked settings, create the ignored file
`SpotSync/SpotSync/local_settings.py`:

```python
import os

from .settings import *  # Local override of the project's development settings.

SECRET_KEY = os.environ["SPOTSYNC_SECRET_KEY"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "spotsync"),
        "USER": os.environ.get("PGUSER", "spotsync_user"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}
```

Set `SPOTSYNC_SECRET_KEY` and any required database credentials through your
private environment or secret manager, then select the override module:

```sh
export DJANGO_SETTINGS_MODULE=SpotSync.local_settings
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

The tests cover accounts, booking creation/cancellation, slot availability,
queues, staff page rendering, and existing route aliases. They run against a
temporary database and do not load historical snapshots or call Google APIs.
They do not establish that every authorization path or browser interaction is
secure. `python manage.py check --deploy` currently reports deployment warnings;
production settings and security fixes remain separate work.

There was no existing linter or CI configuration. For the cleanup's targeted
Python check, optionally run Ruff 0.14.0 from the repository root:

```sh
ruff check SpotSync/accounts --select F,I
```

For deployment, `python manage.py collectstatic --noinput` regenerates
`SpotSync/staticfiles/`; it is unnecessary for Django's development server.

## Google Maps and deployment limitations

The current templates embed a legacy Maps key, while server geocoding looks up
an incorrectly named environment variable. A conventional `GOOGLE_MAPS_API_KEY`
binding alone does not fix the current implementation. Rotate/restrict the
existing key and migrate all map consumers together in the security phase.
Do not put replacement keys, passwords, database dumps, or private `.env` files
in Git. The local override above is for development, not a production deployment
configuration. See [the prioritized follow-up work](docs/cleanup-plan.md).
