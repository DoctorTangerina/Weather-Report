# Issue #13 — Live fetch and fallback

Source: interview with the maintainer on 2026-11-14.
Status: complete design confirmed by the maintainer; implementation authorized.

## Confirmed decisions

- Closing #13 requires integration with the real acquisition from #6. Simulated
  acquisition can support development and automated tests but does not establish
  completion on its own.
- When live acquisition fails, a preloaded example may have a different Region,
  Variable or period. Preserve the example's actual identity and show an explicit
  alert that it is a different, preloaded example rather than the requested data.
- On a cache miss, the HTTP request waits for acquisition within a time limit,
  then returns the result or the fallback. No background-job polling for the MVP.
- If acquisition fails and no usable example is available, return HTTP 503 with
  a clear unavailability message. Ship examples with the application to support
  the demo experience.

## Open decisions

- None identified in the confirmed interview scope.

## Second-round decisions

- Acquisition has an initial 15-second limit, configurable on the server. Validate
  feasibility against #6 before claiming real acquisition works.
- Choose examples deterministically: same Region and Variable first (another
  period allowed), then same Variable in another Region, then another usable
  example. Preserve the actual identity of every example.
- Frontend must present fallback data under its actual Region, Variable and
  period, and must not use it to answer the original investigation. Communicate
  this requirement to the frontend workstream.
- Reject malformed or inverted periods with HTTP 422 before acquisition.

## Dependency update supplied by the maintainer

- #11 is closed. #6 landed in #34 and was reverted in #36; the
  `series-acquisition-and-quality-gate` branch remains available for re-landing.
- Fallback can ship independently of #6, using stored examples and the existing
  `live_data_unavailable` notice code. This does not close the live acquisition
  acceptance criterion.
- #38 already displays the notice. At interview time, DiscoveryScreen
  displays `notice.message`, but chart labels still derive from the requested
  Discovery and the investigation action stays enabled. Showing the notice alone
  therefore does not implement the agreed identity and investigation treatment.

## Frontend handoff

On `notice.code == live_data_unavailable`, explicitly identify a preloaded
example. Resolve labels from the returned series identity, show its actual
period, and prevent substituted data from being used to answer the original
investigation. The notice banner from #38 can be reused.

## Third-round decisions

- Timeout, missing/invalid Earthdata credentials, upstream unavailability and
  quality-gate rejection lead to fallback. Keep public messages simple; retain
  diagnostics on the server without exposing credentials. Do not hide programming
  errors as data unavailability.
- Persist successfully acquired results across API restarts, keyed by Region,
  Variable, period and engine version. Never save a fallback example under the
  requested key.
- A usable example must validate against the series schema, match the current
  engine version and reference a Region/Variable combination supported by the
  current catalog. Skip incompatible examples; return 503 if none remain.
- Required verification: HTTP tests for live success, cache reuse, fallback,
  timeout, 422 and 503, plus an actual acquisition-and-storage run integrated
  with #6. Communicate frontend acceptance criteria from Q7 explicitly.

## Fourth-round decisions

- Always identify examples as "dado pré-carregado", including when their Region,
  Variable and period exactly match the request. When they differ, also disclose
  the difference and preserve their actual identity. An exact preloaded example
  may be served directly; do not imply it was acquired live for the request.
- If live acquisition succeeds but cache persistence fails, return the acquired
  data with HTTP 200 and log the storage failure on the server. A later request
  may need to acquire it again. Successful persistence remains part of the
  completion evidence for the normal live-acquisition flow.

## Confirmation boundary

These decisions describe the intended behavior, not implemented functionality.
The maintainer confirmed the complete design and invoked `implement`.

## Fifth-round decision

- Distinguish provenance in the UI: "dado pré-carregado" for shipped examples;
  "dado em cache" for previously acquired live data served from storage. Do not
  reuse `live_data_unavailable` for an ordinary successful cache hit: that code
  remains the fallback signal. Keep provenance separate from failure semantics
  when implementing the response contract and frontend handoff.

## Implementation boundary

The initial implementation was based on the older main frontend. Resolving PR
#43 against its current `data-engineering` base preserves the #38 globe UI and
#16 comparison API. DiscoveryScreen remains deleted; MainScreen and DiscoveryPanel
now adopt the provenance contract, actual example identity/highlights and
substitution guard. InvestigationScreen keeps the same guard for direct entry.
The hook retains the `series` and `notice` fields expected by the integrated UI
alongside per-response provenance.

After #6 closed, its monthly catalog Series pipeline and downloader were integrated
through a cancellable worker. HTTP integration is verified with synthetic NetCDF
files; a real authenticated NASA run still requires an Earthdata token in this
environment. No real-data proof is inferred from #6 being closed.
