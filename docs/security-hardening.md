# Security and booking hardening

This phase builds on `f5b82ea` (the first cleanup branch). It changes no database
fields or migrations and does not migrate/rewrite existing user or booking data. Main is not merged into or
modified. Compatibility risks were reported before the security/dependency
implementation; the rollout details below distinguish corrections from
remaining operational work.

## Credential assessment and operator actions

No secret values, hashes, session identifiers, or decoded payloads are included
here or in test output.

| Finding | Evidence and treatment |
| --- | --- |
| Former embedded Django signing key | A real functional signing secret: offline verification accepted three historical exported session signatures with it. Removed from current configuration. Supply `SPOTSYNC_SECRET_KEY` privately; no old-key fallback is retained. |
| Former embedded database password | A configured credential, not proof of access to a live remote database. Local PostgreSQL uses trust authentication, so password validity elsewhere is unverified. Removed the fallback; settings now read standard `PG*` variables. Rotate any deployment that used it. |
| Former embedded Maps key | Credential-shaped API key present in five templates and an incorrectly named environment lookup. Live validity, project ownership, and restrictions are unverified; no live requests were made with it. Remove/restrict or rotate it through the owning Google project. Server/browser keys now use separate bindings. |
| User/session exports and SQLite snapshot | JSON exports contain real-format password hashes and session records; the embedded signing key verified historical session signatures. All three exported sessions have expired by the audit date. Account currency and credential reuse are unknown. Data-bearing files remain unchanged to preserve data compatibility; do not import or redistribute them casually. |

Removing literals does not erase Git history, revoke an API key, rotate a
database password, or invalidate every historical credential. Those operations
require the operator's access to the owning systems. Do not rotate by committing
a replacement value. Review historical-data retention and any coordinated
history cleanup separately, with recoverable backups and owner agreement.

The application reads `SPOTSYNC_SECRET_KEY` directly. This is a local signing
secret, not a network-proxy token. Supply an actual private process binding,
not a placeholder intended to be replaced in an HTTPS request. A development
process without a key generates a fresh random one; production
(`SPOTSYNC_DEBUG=false`) fails closed without an explicit key. The prepared
cloud startup uses a private generated development key outside the repository.

Rotating the signing key invalidates existing sessions and password-reset
tokens. Deploy all workers with the same private key. Database deployments that
relied on the old literal must set `PGPASSWORD`; the schema, default database
name, and role name are unchanged. Browser Maps keys are intentionally visible
in HTML and must have API/referrer restrictions. Server credentials are never
rendered as a browser fallback.

## Access-control policy and fixes

Anonymous requests to staff endpoints require login. Authenticated customers,
foreign-business staff, inactive accounts, and invalid staff roles cannot use
business privileges. A central decorator and model permission check enforce
business membership plus the existing explicit role capability. Superusers
retain the central model's administrative bypass.

| Operation | Required privilege |
| --- | --- |
| Read/edit business information | Same-business `can_edit_info` |
| Read/edit services and hours | Same-business `can_edit_service` |
| Read staff and role settings | Same-business `can_edit_staff` |
| Change role permissions | Same-business owner (or superuser); this remains possible even if the owner's edit-staff flag is unchecked |
| Add/edit/remove staff | `can_edit_staff` plus role restrictions; targets must belong to the supplied business when editing/removing |
| View customer bookings / change their statuses | Same-business `can_display_customers` |

Owners can manage staff roles but cannot change their own role through the staff
editor; owners cannot be removed through the delete endpoint. Managers cannot
edit owners/other managers or assign owner; the prior editor's ability to
promote a worker to manager is retained. Workers cannot add/edit/remove staff
even if granted the staff-list capability. Unsupported role values, malformed
JSON, invalid/duplicate emails, and cross-business staff IDs fail without writes.
The owner-management command remains available for explicit administrative work.

Permission editing is now owner-only; clients that previously modified role
settings without that authority receive a denial. Queue removal is POST-only
(the existing UI already uses POST). CSRF middleware is retained. Customer
booking details/cancellation remain scoped to the booking's user.

The custom email backend now rejects inactive/ambiguous accounts rather than
raising on duplicate historical emails or authenticating an inactive user.
No email-uniqueness migration or user-record rewrite is introduced. The legacy
set-password endpoint now requires login and redirects to the existing login
route; the token-based reset routes remain unchanged.

Editable staff names/emails and service labels are escaped before insertion
into HTML, including quoted attributes. This closes the reviewed dynamic HTML
injection paths without replacing the UI or introducing a frontend dependency.

## Dependencies

The updated runtime pins are Django **5.2.17** (LTS), Pillow **12.3.0**, and
sqlparse **0.6.0**. The Python 3.12 environment and existing PostgreSQL schema
remain compatible. Existing asgiref, psycopg2, tzdata, and Requests pins remain
unchanged. Linux cloud validation uses the same-version psycopg2-binary
development substitute; source psycopg2 still requires libpq development tools.

The full installed Python dependency graph passed `pip-audit` with no known
vulnerabilities at validation time and passed `uv pip check`. This is a dated
dependency scan, not a guarantee about operating-system packages, PostgreSQL,
browser CDNs, future advisories, or the obsolete committed Windows environment.
The latter remains inactive and must not be used to run the application.

## Booking and queue corrections

- The landing page compares reservation text times with normalized appointment
  times, avoiding the same-day type-comparison crash.
- Availability endpoints reject missing/malformed dates and nonpositive/null
  intervals with HTTP 400 rather than crashing or running unbounded loops.
  Existing invalid configuration is not silently rewritten.
- Creation endpoints validate configured options/reasons and the advertised
  schedule: future working-day slots, within hours, aligned to the interval.
  Clients posting arbitrary, past, closed, or off-grid slots now receive an
  error; the published UI already presents configured slots. Invalid payloads
  use HTTP 400; occupied/unavailable slots retain a JSON `success: false` result.
- Business-row locks serialize competing customer booking requests, including
  appointments and reservations with null options. Staff reactivation cannot
  create a second active appointment in an occupied slot. Existing status
  choices are enforced per booking type.
- Queue model saves/deletes and queue endpoints use the same transaction lock.
  Joining, replacement, cancellation, reactivation, removal, and estimate-setting
  edits recalculate active positions, individual estimates, and business totals
  together. Queue ordering breaks timestamp ties by primary key. Existing
  public method signatures and the queue-delete return behavior are preserved.
  Queue joins return the saved position even when legacy positions have gaps.
- The business detail GET no longer writes queue counters. Business information
  updates save only their own fields, avoiding stale queue-counter overwrites.
  Zero-valued geocoded coordinates are retained.
- Geocoding uses structured request parameters, a bounded timeout, status/JSON
  handling, and generic failure logging that does not include credential URLs.
  Missing/failed geocoding preserves existing/manual coordinates.

### Deliberately unresolved schema issue

The reservation uniqueness constraint includes cancelled rows with a non-null
option. Rebooking those exact keys safely requires a reviewed constraint
migration and an audit of existing duplicates/null-option semantics. This phase
keeps history and the constraint intact. Availability now honestly marks such
slots unavailable, matching creation behavior. It does not delete old bookings,
reuse another customer's row, or change stored option text to bypass uniqueness.

Application locks protect the tested web/model workflows on PostgreSQL. Direct
SQL, reservation/appointment admin writes, and queryset bulk updates bypass
some service/model invariants. Database constraints are still needed for
universal enforcement, and SQLite does not provide PostgreSQL row-lock semantics.
Historical duplicates are not silently removed. Schema repair and bulk-write
semantics remain follow-up work.

## Verification and remaining limits

Run Django's `accounts` suite on PostgreSQL, Node's dependency-free escaping
tests, targeted Ruff checks, Django system/migration checks, and the dependency
audit. PostgreSQL concurrency tests use real independent connections and
simultaneous requests. Test databases and temporary uploads/static outputs are
separate from retained data. Maps behavior is tested with mocked responses,
not live credentials or external quota.

Production cookie/TLS settings and email delivery remain deployment work.
Data-bearing exports, committed Windows packages, generated static files, and
uploads remain unchanged. Credential rotation and history/retention decisions
require operator action. This phase is not a complete penetration test or a
production-readiness claim.

Validation results (2026-10-15): **55 Django tests passed**, including four
PostgreSQL concurrency tests with no skips; **three Node escaping tests passed**.
All 34 route patterns/names/callback references match phase one. Ruff checks,
template compilation, rendered JavaScript syntax with and without browser Maps
configuration, static collection, Django system checks, and migration checks
pass. A fresh HTTP server verified CSRF-protected email login, authenticated
pages, denied permissions, and session persistence across a server restart.
The installed graph contains 11 Python packages and has zero advisories in the
recorded audit; package compatibility checks pass. Five development deployment
warnings remain (W004, W008, W012, W016, W018).

The reusable cloud install/start draft was updated and exercised with the new
pins and private development signing-key initialization. The key file is
outside the checkout with mode 0600; saved instructions contain no key value.
Saving this draft does not publish the environment. Existing data snapshots,
migrations, uploads, collected static files, and the inactive Windows environment
were checked against the phase-one branch and are unchanged.
