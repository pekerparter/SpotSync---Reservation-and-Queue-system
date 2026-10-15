# Google Maps configuration and operator actions

Phase 3 reviewed the active settings, context processor, geocoding helper, and
five Maps templates. The Phase 2 implementation is retained unchanged. Server
geocoding reads only `GOOGLE_MAPS_API_KEY`; the template context supplies only
`GOOGLE_MAPS_BROWSER_API_KEY`. There is no fallback between them. No key-shaped
Google credential remains in maintained active source. Historical Git contents
are outside that claim and were not used to make requests.

## Manual Google Cloud work

1. In the owning Google Cloud project, inventory old credentials in **APIs &
   Services > Credentials**. Treat every previously committed key as compromised.
   Revoke/delete the exposed keys. If an immediate cutover would interrupt a
   deployment, restrict the old keys while arranging a prompt replacement and
   revocation; do not keep using a historical key as a permanent solution.
   Review usage, billing, quotas, and unexpected traffic. No leaked key was
   tested during this review.
2. Use an appropriate billing-enabled project. Enable **Geocoding API** for the
   server and **Maps JavaScript API** for browser maps. The current templates
   load `libraries=places`, and the business editor uses legacy
   `google.maps.places.Autocomplete`; enable the corresponding **Places API**
   only if the project is eligible for that legacy API. Merely enabling Places
   API (New) does not migrate this widget. New-project eligibility may require a
   separately reviewed migration to Google's new Places widget. Basic maps and
   server geocoding can be configured independently.
3. Create two separate credentials in Google Cloud. Keep their values in private
   deployment/environment bindings, never in source, documentation, screenshots,
   PR text, or committed `.env` files. No API key is created by Phase 3 or CI.
4. Restrict the **server** credential to **Geocoding API** and to the application's
   known server egress IP addresses. IP restrictions must match actual outbound
   addresses, including a managed proxy/NAT where applicable. Arrange stable
   egress for hosts with dynamic addresses; do not solve this by removing
   restrictions. Set it as `GOOGLE_MAPS_API_KEY` only on backend processes.
5. Restrict the **browser** credential to HTTP referrers for the exact deployed
   sites, for example `https://your-domain.example/*`, with only the supported
   Maps JavaScript/Places APIs. Use a separate development browser credential
   with narrow localhost/127.0.0.1 referrers if needed. Do not allow arbitrary
   websites. Set it as `GOOGLE_MAPS_BROWSER_API_KEY`; visibility in rendered HTML
   is expected and is why restrictions matter.
6. Configure usage quotas, billing alerts, and access to credential administration.
   Restart/redeploy backend workers after changing environment bindings. Verify
   ordinary maps, address autocomplete where eligible, and geocoding with the
   **new authorized** credentials. Inspect Google Cloud metrics and browser
   errors without copying key-bearing URLs into public tickets/logs. This live
   operator check was not performed by Phase 3.
7. Confirm revocation of superseded credentials. Separately rotate any exposed
   Django/database credentials and review retention of sensitive exports using
   [the Phase 2 rollout notes](security-hardening.md). This phase neither rewrites
   Git history nor deletes historical records.

## Behavior and verification

- Missing server credential: no HTTP request; existing/manual coordinates remain.
- Missing browser credential: no SDK request; map/autocomplete remain inactive,
  while ordinary page/form rendering continues. There is currently no dedicated
  explanatory Maps-disabled UI.
- Geocoding uses structured parameters, a five-second timeout, HTTP status/JSON
  handling, and generic failure logging. Provider error payloads are not exposed
  in responses/logs; errors return `(None, None)` to the business editor.
- Existing tests cover missing credentials and successful/failed geocoding.
  Phase 3 adds mocked checks for browser/server isolation, timeout/HTTP failures
  containing a synthetic credential URL, malformed JSON, and denied payloads.
  Tests make no authenticated Google request, consume no quota, and cannot
  validate live billing, key validity, restrictions, or project eligibility.

Future browser tests should cover SDK-load/auth failures, unavailable Places,
missing coordinates, and coordinates on latitude/longitude zero. The current
editor uses a truthiness check for its initial center, so zero-coordinate browser
centering deserves follow-up even though server geocoding retains zero values.
Keep that UI behavior change outside this repository-hygiene phase.
