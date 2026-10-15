# Repository audit and cleanup plan

Audited at baseline `694ace7` on 2026-10-15. Phase one deliberately preserves
URL paths/names, model fields, migrations, status values, permissions behavior,
and booking rules. Findings below distinguish confirmed failures from risks
that need further testing. No credential values or user records are reproduced.

## Architecture and inventory

- One Django 5.1 application, `accounts`, handles customers, business staff, and
  admin. `views.py` mixes HTML pages, JSON mutations, availability generation,
  and Google geocoding in roughly 1,000 lines. There is no service/API layer.
- `CustomUser` extends Django's user with a business and staff role. Businesses
  have categories, weekly hours, queue counters, booking intervals/options,
  coordinates, and per-role permissions. Queue model save/delete hooks update
  counters and positions; a business post-save signal creates default hours.
- Reservations store time as text; appointments and queues use `TimeField`.
  Reservation uniqueness includes business/date/time/option but not status.
- Server-rendered templates share a base layout and contain inline JavaScript.
  They call Django JSON routes and load Tailwind/Google Maps externally. There
  is no package.json, frontend build, CI workflow, or configured test/lint runner
  beyond Django. The original test module contained no tests.
- Baseline: 7,049 tracked files, including 6,739 Windows virtual-environment
  files, 131 collected static files, 70 uploaded images, a SQLite snapshot,
  several JSON snapshots, and two empty root dump placeholders. These are
  distinct from the application's source static assets and migrations.

## Priorities

| Priority / phase | Change and reason | Compatibility and validation |
| --- | --- | --- |
| P0 / security follow-up | Require authentication and business-scoped authorization on every staff/permission mutation; scope target staff to the business. | Changes who may access endpoints. Define owner/manager/worker rules and add negative tests before rollout. |
| P0 / security follow-up | Rotate exposed Django/database/Maps credentials, move configuration to private bindings, and review tracked user/session exports. | Requires operational coordination; removing text from the current tree does not revoke credentials or erase Git history. |
| P1 / phase one | Consolidate imports, use explicit model/view references, remove shadowed definitions and unused imports/assignments. | Preserve the effective method implementation, callbacks, decorators, routes, and database effects. |
| P1 / phase one | Declare the imported `requests` dependency; normalize UTF-16 requirements to UTF-8. | Keep existing dependency versions; use a tested Requests version without the advisories found in the local 2.32.5 installation. |
| P1 / phase one | Add root ignore rules, README, regression coverage, and remove the two zero-byte root dump files. | No data-bearing snapshots, uploads, source assets, or migrations are deleted. Ignore rules do not untrack existing files. |
| P1 / phase one | Handle businesses with no image in the portal and information editor. | `image` is optional in the model. Guards avoid confirmed page-rendering errors; existing images and the upload preview remain available. |
| P1 / dependency follow-up | Upgrade Django to a supported line and address Pillow/sqlparse advisories. | Framework/image/parser upgrades need compatibility testing; do not silently change pins as an import-cleanup side effect. |
| P1 / booking follow-up | Normalize date/time comparison; validate slot/date/interval inputs; handle cancelled reservation uniqueness and concurrent booking/queue updates. | Business rules, schema constraints, and error contracts require focused tests and possibly migrations. |
| P2 / artifact follow-up | Remove tracked Windows `venv/` and generated `staticfiles/` after verifying reproducible installs/collection. Review snapshots for retention, anonymization, or secure archival. | Thousands of deletions deserve a separate mechanical change. Preserve uploads and source assets; do not assume a snapshot is dispensable merely because default settings use PostgreSQL. |
| P2 / organization follow-up | Split views by feature, extract repeated slot-generation/booking helpers, and move inline scripts into maintained static modules. | Start after broader coverage. Preserve public imports, route aliases, error messages, ordering, decorators, and model save side effects. |

## Security and correctness findings

### Confirmed with isolated database diagnostics

- `update_role_permissions` accepts a POST from an anonymous client and changes
  permissions without any application authentication/authorization check. The
  standard Django CSRF middleware still applies; CSRF is not an authorization
  boundary. Related `get_role_permissions` data is publicly readable.
- A worker for one business can GET another business's `edit_service` page
  without a permission grant. That view also has no business/permission check
  before its POST update. `Business.user_has_permission` checks role permissions
  but not business membership, so other callers also need a membership review.
- `landing_page` raises a type-comparison error when a reservation and an
  appointment fall on the same date: reservation time is text and appointment
  time is a `datetime.time` object.
- A cancelled reservation with a non-null option can be advertised as available
  yet cannot be rebooked because the database uniqueness constraint includes
  cancelled rows. Null options and appointment concurrency need separate review.
- The business portal and business information editor raise an error when
  rendering `business.image.url` for an image-less business. Phase one fixes
  these two rendering errors; the other confirmed failures remain follow-up.

Diagnostics ran in Django's disposable test database, without external services
or changes to real user data. The regression suite preserves supported customer
and staff flows; its passing result does not resolve the deferred defects.

### Additional issues found by source review

- `update_staff_member` lacks a login guard and fetches a staff ID without
  constraining it to the supplied business. Role updates and adding staff accept
  values without complete role/ownership validation. Review all mutations
  together rather than fixing one entry point and leaving equivalent bypasses.
- `EmailBackend.authenticate` omits Django's inactive-user check and duplicate
  email handling. Forms validate email uniqueness but the model does not enforce
  it. Direct backend callers, admin/import paths, and concurrent registration
  need explicit tests; login forms may provide additional inactive-user checks.
- `SetNewPasswordView` is not login-protected and redirects to a route named
  `login` that is not declared. Verify its intended relationship to the standard
  token-based password-reset routes before replacing or removing it.
- Missing/malformed slot dates can raise errors; nonpositive/null booking
  intervals can break or prevent slot-generation loops from terminating.
  Creation endpoints do not fully enforce the hours/availability displayed by
  the UI. Appointment availability and creation are vulnerable to races.
- `remove_from_queue` mutates state without a POST-only decorator. Some GET
  handlers also update counters. Queue save/delete/bulk-update paths maintain
  positions and estimated wait times differently and need concurrency tests.
- Several handlers return raw exception text. Google geocoding interpolates a
  URL without structured parameters, timeout, status checks, or error handling.
  Some JavaScript builds `innerHTML` from editable names/emails/service options;
  replace this with safe DOM construction and test stored/DOM injection cases.
- Settings contain legacy credentials, `DEBUG=True`, and development cookie/TLS
  defaults. Six deployment checks warn (W004, W008, W009, W012, W016, W018).
  JSON snapshots include user records and sessions. Treat their contents as
  sensitive; do not publish them as documentation examples or load them blindly.
- `populate_db` deletes categories/businesses and cascades to bookings. It may
  miss static image names on case-sensitive filesystems. Make destructive
  behavior explicit before future management-command redesign.

## Dependency review

The six original pins are used: Django is the framework; Pillow supports
`ImageField`; psycopg2 supplies PostgreSQL connectivity; asgiref/sqlparse are
Django dependencies; tzdata supplies timezone data on platforms without it.
No original runtime dependency is proven removable. `random` was an unused
standard-library import, not a package requirement. `requests` is imported by
geocoding but was absent from requirements; phase one declares it.

A `pip-audit` scan of the original pins with the prepared environment's
same-version `psycopg2-binary` substitute and supplemental `requests==2.32.5`
reported advisories for Django 5.1.7, Pillow 11.1.0, sqlparse 0.5.3, and Requests
2.32.5. Advisory results may contain duplicate records and are not proof that
every issue is reachable in this app. Phase one adds Requests 2.33.0; the
framework/image/parser updates remain higher-risk follow-up work. The binary
PostgreSQL adapter is a local development alternative, not a changed project
dependency. A dependency audit is not a scan of the PostgreSQL server, bundled
libraries, browser CDNs, or inactive vendored Windows environment.

## Unused and redundant code decisions

Removed the earlier `Business.update_people_in_queue` definition: Python already
replaced it with the later method. The surviving method still returns `None`;
adding the earlier method's return value would change behavior. Retained the
public `get_people_in_queue` method even though no internal caller was found.

Removed the first JavaScript `updateHiddenInput` declaration in the service
editor; the later declaration was already effective and remains unchanged.
Kept the random-shuffle template filter because the categories template uses
it. Kept `EditServiceForm`, legacy routes (including both reservation aliases
and the doubled accounts prefix), password-reset URLs, migrations, exports,
and image assets: internal non-use alone is insufficient evidence to remove
a public class, link target, compatibility alias, or data-bearing file.

## Phase-one review and validation

Review the source/import changes separately from regression tests and docs.
Only the two root empty dump placeholders and the relocated nested ignore file
are deleted. No migration, schema, credential, permission, or booking-rule
change is included. The only functional correction is safe rendering when a
business has no optional image.

Required checks are the Django regression suite against PostgreSQL, normal
system checks, migration consistency, unchanged route contracts, and targeted
Ruff F/I checks on `accounts/`. There is no frontend build target. Deployment
warnings and dependency advisories remain distinct follow-up findings; do not
describe the application as production-ready because the cleanup tests pass.

Validated in the prepared Linux/Python 3.12/PostgreSQL 17 environment:

- All 18 regression tests pass. Running the first 17 tests before the cleanup
  exposed the optional-image rendering error; the original suite had zero tests.
- All 34 account route patterns, names, and callbacks match the baseline;
  32 representative reverse lookups also match, including compatibility aliases.
- Django system checks, migration consistency, and applied-migration checks
  pass. All account templates compile.
- Ruff F checks pass across project Python code; F/I checks pass in `accounts/`.
  Rendered service-editor JavaScript passes Node's syntax check.
- Static assets collect successfully to a directory outside the checkout, and
  the README's local settings example executes successfully.
- The final installed-dependency audit still reports advisories in Django,
  Pillow, and sqlparse; Requests 2.33.0 has none in that scan. The audit's failure
  is an outstanding security finding, not a passing cleanup check.
- Existing source static assets, uploaded images, database snapshots, migration
  files, legacy settings, and the committed Windows environment are unchanged.

The saved cloud install instructions were updated and rerun to accept both the
baseline UTF-16 and normalized UTF-8 requirements. This keeps the prepared cloud
environment compatible with either revision; it does not publish that draft.
