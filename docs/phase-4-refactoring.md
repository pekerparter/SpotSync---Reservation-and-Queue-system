# Recommended Phase 4: incremental application organization

This is a proposal, not a refactor implemented by Phase 3. Keep current routes,
response shapes, role capabilities, ordering, transaction boundaries, database
schema, migration history, and model method side effects stable throughout the
organizational work. Schema/data changes require a separate reviewed proposal.

## Current boundaries and proposed layout

`accounts/views.py` is about 850 lines covering login/reset/profile pages,
customer discovery, queues, availability, booking mutations, staff roles,
business configuration, and HTTP geocoding. `bookings.py` already centralizes
slot generation/validation, and `permissions.py` centralizes business access and
role assignment. Build on those boundaries rather than introducing another app
or framework immediately.

| Area | Suggested organization | Compatibility precautions |
| --- | --- | --- |
| Views | `accounts/views/{auth,customers,bookings,queues,business,staff}.py` with `views/__init__.py` re-exports | Preserve `accounts.views` public imports/callbacks, decorators and URL aliases; moving functions also changes mock patch locations |
| Read queries | `accounts/selectors/{bookings,queues,businesses}.py` if repeated queries justify it | Preserve filters, visibility, ordering, related-object behavior, and read/write side effects |
| Mutations | `accounts/services/{bookings,queues,staff,businesses}.py` | Extract one atomic operation at a time with explicit actor/input; keep business-row locks and queue recalculation in the same transaction |
| Maps | `accounts/integrations/maps.py` | Keep credential separation, structured parameters, timeout, generic logging and fallback semantics; patch tests at the actual call site |
| Models | Initially retain `models.py`; consider `models/{users,businesses,bookings,queues}.py` only after service extraction | Re-export models and preserve app labels/table names, signal registration, migration import paths, and save/delete contracts |
| Signals | Explicit `signals.py` registered once through `AccountsConfig.ready()` if extracted | Business creation must still create default hours exactly once; test migration/startup behavior |
| Templates | Existing template names plus small includes for business cards, booking rows, hours, map placeholders, and form errors | Avoid changing navigation, CSRF handling, element IDs, or escaping during extraction |
| JavaScript | `static/accounts/js/{maps,staff,service_editor,bookings}.js` beside existing `escape_html.js` | Supply configuration via safely encoded data/`json_script`; retain route reversal, CSRF, API response handling and optional Maps loading |
| Tests | Move existing tests into feature modules under a test package when worthwhile | Preserve discovery and all concurrency tests; first record the baseline suite/count to detect accidental loss |

Do not split models solely to reduce line counts. Queue hooks and the business
post-save signal have meaningful side effects that must be mapped before moving.
`Business.get_business_hours()` can create missing rows on access, and queue
save/delete hooks maintain estimates and counters. A first service extraction
should delegate to these hooks, with no duplicate recalculation. Replacing hooks
or extending invariants to admin/bulk paths is separate behavior work.

## Reuse and business-logic separation

- Reservation and appointment handlers repeat type dispatch, option/reason
  validation, status handling, and availability/creation plumbing. Extend the
  existing booking helpers through small explicit functions; do not erase
  differences between text reservation times and appointment `TimeField` values
  or between their uniqueness rules.
- Queue joins, replacements, cancellations, status changes, and business service
  edits all depend on one locked queue ordering/counter operation. Establish one
  clearly owned mutation interface while preserving current model hooks.
- Staff pages/API mutations combine authorization, JSON validation, role policy,
  persistence, and response construction. Keep the central permission decorator
  and role policy; extract reusable validation without weakening ownership or
  cross-business checks.
- `edit_service` manually handles fields/options/hours while `EditServiceForm`
  overlaps part of that validation. Audit callers before reuse/removal: adopting
  the form can change empty-list/null behavior and validation contracts.
- Registration/profile forms duplicate email checks. Share a validation helper
  only after testing case/duplicate semantics; introducing email uniqueness is a
  database/data project, not an organizational shortcut.
- Maps templates repeat SDK initialization and markers. Staff/service editors
  share escaping, fetch/CSRF, modal, and dynamic DOM patterns. Extract tested
  modules while retaining the existing escaping helper. Prefer text/DOM APIs
  over fresh string interpolation.
- Several staff handlers repeat permission checks after the decorator. Remove a
  duplicate only when tests prove both entry paths enforce the same policy and
  response contract. Preserve deliberate superuser and owner exceptions.

## Coverage to add before moving behavior

1. Capture all account and root URL patterns/names/reverse behavior, including
   both reservation aliases, duplicate password-reset names, the doubled
   accounts prefix, and callback import references. Treat odd paths as public
   compatibility contracts until a deprecation is explicitly agreed.
2. Expand permission matrices for anonymous/inactive/customer/foreign staff,
   owner/manager/worker/superuser, malformed JSON, CSRF, unsupported methods,
   staff self-changes, and owner deletion/promotion boundaries.
3. Add full browser tests for staff/service DOM updates, escaping, modal actions,
   booking submission and failure messages, CSRF, Maps-disabled pages, SDK
   failures, Places eligibility failures, missing/zero coordinates, and uploads.
4. Extend PostgreSQL races to cancellation/reactivation, estimate changes during
   joining, different businesses, rollback paths, and queue tie ordering.
   Keep real independent connections and explicit lock expectations.
5. Exercise DST/timezone boundaries, closed/overnight schedules and invalid
   intervals, optional/null/empty booking options, status transitions, mixed
   reservation/appointment display, and query counts on busy listings.
6. Add upload validation/storage isolation, management-command safety, default
   hours/signal behavior, direct model hook contracts, and password-reset email
   rendering. Document where admin/queryset/direct SQL bypass invariants before
   changing those paths.

## Safe sequence

1. Record route/response contracts and add tests for the first feature to move.
   Keep each PR limited to one feature. Run the full PostgreSQL suite, Node,
   Ruff, static collection, and migration checks through CI.
2. Extract Maps and small pure input helpers first, retaining compatibility
   imports and updating mocks to intercept real call sites. Avoid changing
   error messages or credentials while moving code.
3. Extract read queries, then one booking/queue/staff mutation behind the existing
   view. Keep transaction ownership and lock acquisition order explicit; verify
   rollback/concurrency before proceeding. Avoid temporarily implementing the
   same operation in both a service and a model hook.
4. Convert `views.py` into a package with re-exports in a dedicated PR. Compare
   every URL and response contract with the recorded baseline; inspect named
   imports and mock paths as well as user-visible navigation.
5. Move one inline script/shared template fragment at a time, supported by browser
   tests and safe configuration encoding. No frontend framework is necessary.
6. Consider a model package only when services/tests provide clear boundaries.
   Require `makemigrations --check --dry-run` to remain clean. Roll back each
   organizational PR by a normal revert if needed; never rewrite history.

Cancelled-reservation uniqueness, universal booking constraints, duplicate
historical emails, data retention, production configuration, and modern Places
migration need separate decisions. Do not bundle them into file moves or silently
repair historical records during Phase 4.
