# Phase 3: repository hygiene, CI, and documentation

Validated locally on 2026-10-15. Work starts at fetched `main` **4e0a149**, the
merge of Phase 2 PR #3, with hardening commit **b921ad4** verified as an ancestor.
Phase 3 branch: `cleanup/phase-3-repository-hygiene`. No main merge, history
rewrite, force-push, schema change, or booking/queue logic change is included.

## Repository audit and removal decisions

The review read `cleanup-plan.md` and `security-hardening.md` before removing
anything. It distinguished generated output from source assets and retained
data. File contents of snapshots/exports were not published as audit output.

| Inventory on latest main | Files | Decision / evidence |
| --- | ---: | --- |
| Windows `venv/` | 6,739 | Untrack; fresh Python 3.12 install succeeds from the unchanged runtime requirements |
| Collected `SpotSync/staticfiles/` | 131 | Untrack; all 131 relative paths regenerate with current Django |
| Source `SpotSync/static/` | 20 | Retain; checksums unchanged and all assets appear byte-for-byte in new collected output |
| Uploaded `SpotSync/media/` | 70 | Retain every existing upload unchanged |
| SQLite and JSON snapshots | 5 | Retain unchanged; potentially sensitive historical data, not test fixtures |
| Migration directory | 33 | Retain 32 numbered migrations plus `__init__.py`, unchanged |
| Other source/docs | 59 | No other committed cache/log artifact justified removal |

The 6,870 generated files total 60,862,411 bytes (about 58 MiB uncompressed).
They are removed from tracking in dedicated mechanical commit **b5f7cb0**,
separate from configuration/tests/documentation. `git rm --cached` leaves local
copies intact; new clones will not contain them. Their history remains in Git,
so this change does not shrink old Git objects or erase historical credentials.
Existing clones should use a fresh `.venv`, never the obsolete Windows packages.

A pre-removal checksum manifest verified all 185 retained files other than the
intentionally edited README/ignore rules. This includes every retained export,
upload, migration, source asset, existing test, model, view, template, and URL
module. No additional data cleanup is authorized by this phase.

`.gitignore` retains private-config, environment, media/export, and static-output
rules and adds common build/package, tool, coverage, and scratch artifacts.
Ignore probes confirm environments, caches, uploads, secrets, build outputs,
and collected static output are ignored. Existing data/media remain tracked;
ignore rules prevent new accidental additions, not removal of existing records.

## Maintenance and CI changes

- `requirements-dev.txt` includes the unchanged runtime requirements and Ruff
  0.14.0. No runtime pin is removed or substituted.
- `pyproject.toml` records Python 3.12 and Ruff F checks across maintained Python;
  the second CI command retains import-order checks in `accounts`. Generated
  files and migrations are outside that lint scope. No broad formatting rewrite.
- `.github/workflows/ci.yml` runs on PRs and pushes to main with Python 3.12,
  Node 22, PostgreSQL 17, read-only repository permissions, a 15-minute timeout,
  and cancellation of obsolete runs. It installs native build prerequisites and
  exact runtime/dev requirement roots, checks dependency compatibility, runs
  Python/JavaScript tests and lint, checks settings/migrations, migrates an empty
  service database, and collects static assets. Failed commands fail the job.
- Opt-in `SpotSync.ci_settings` requires a temporary output directory, isolates
  media/static output, and disables live Maps bindings. CI supplies disposable
  PostgreSQL credentials and an ephemeral masked signing key. It imports no
  historical data and requires no deployment/Google Cloud secrets.
- README now covers the actual project, stack/layout, PostgreSQL provisioning,
  private environment variables, startup, management commands, isolated checks,
  CI, Maps, and deployment limitations. `.env` is explicitly not auto-loaded.
- [Maps operator checklist](google-maps.md) documents old-key revocation,
  separate credentials, restrictions, APIs, Places eligibility, quotas and
  private deployment. [Phase 4 plan](phase-4-refactoring.md) proposes incremental
  module/service/template/JavaScript changes and prerequisite tests.

## Google Maps review

The Phase 2 active implementation is correct for the requested credential and
error-handling boundaries and is unchanged. Server geocoding uses only
`GOOGLE_MAPS_API_KEY`; browser templates receive only
`GOOGLE_MAPS_BROWSER_API_KEY`. Missing server credentials skip HTTP requests;
missing browser credentials omit the SDK. Failure preserves existing/manual
coordinates. Transport/JSON errors log a fixed generic warning; provider error
payloads are neither logged nor returned to the client.

A scan of maintained active source finds no Google key-shaped literals. Existing
missing-key/mocked tests pass. Six new mocked tests cover browser context and
all five Maps templates, server request parameters, transport/HTTP error-log
redaction, denied responses, and malformed JSON. No historical key, live Google
credential, authenticated Google request, or quota was used.

Live key validity, billing, revocation, restrictions, and Places eligibility
require the owner's Google Cloud work. The editor's initial-center truthiness
check for zero coordinates and richer Maps-disabled/SDK-failure UI are documented
future browser work, without changing application functionality here.

## Local verification

| Check | Result |
| --- | --- |
| Fresh Python 3.12.14 environment, unchanged `SpotSync/requirements.txt` | PASS; all declared runtime packages installed, including compiled `psycopg2==2.9.10`, with no binary-package substitution |
| `pip check` | PASS; no broken requirements |
| Full Django discovery (`manage.py test --noinput --verbosity 2`) | PASS; 61 tests: existing 55 plus six Maps tests, all four PostgreSQL concurrency cases executed, no skips |
| JavaScript (`node --test tests/*.test.cjs`) | PASS; all three tests, local Node 24.19.0 (CI selects Node 22) |
| Ruff 0.14.0 (`ruff check .`; accounts import ordering) | PASS |
| Django `check --fail-level WARNING` | PASS; no normal system-check issues |
| `makemigrations --check --dry-run` | PASS; no model changes detected |
| Empty disposable database migration and `migrate --check` | PASS; all existing migrations apply |
| `collectstatic --noinput` | PASS; 147 current assets, every old collected path reproduced and all 20 source assets identical |
| Retained-file checksums and URL module comparison with 4e0a149 | PASS; retained source/data unchanged, both URL modules unchanged |
| Ignore probes and tracked generated-file inventory | PASS; no tracked files remain in either generated directory |
| Workflow validation, actionlint 1.7.7 | PASS; schema, expressions, events and action inputs checked locally |
| Git diff whitespace check | PASS |

Local PostgreSQL uses a newly initialized isolated cluster/database under the
workspace's scratch area; the disposable role/database contain synthetic test
data only. It does not connect to the retained application database. Test media
and collected assets go outside the checkout. The cloud's extracted libpq headers
and GCC were supplied explicitly to build the declared source adapter; normal
CI/local system packages provide these prerequisites.

## Remaining work and limits

- Remote GitHub Actions status must be assessed from an actual run after PR
  creation. A local pass/actionlint validation is not a remote Actions pass.
- Manually revoke old Maps credentials, apply separate API/referrer/IP
  restrictions, and rotate other historically exposed credentials. No new API
  credential is created or committed by this phase.
- Decide secure retention/archival of historical snapshots and uploads with the
  owner. This branch preserves all such files and does not rewrite history.
- Deployment still needs production host/CSRF/TLS/cookie settings, a stable
  private signing key, email delivery, a production app server, static/media
  serving, backups, and restricted application database privileges. Base
  development settings retain five deployment warnings documented in Phase 2.
- Direct dependencies and Ruff are pinned; a full transitive lockfile, image
  digest pinning, ongoing vulnerability scans, and broader browser coverage are
  possible follow-ups. Installing dependencies does not certify their future
  vulnerability status; no new vulnerability audit is claimed here.
- Existing cancelled-reservation uniqueness and bulk/admin invariant bypasses
  remain as documented in Phase 2. Do not repair them via unreviewed schema/data
  changes during file organization work.
