# Issue #13 — merge verification

PR #43 now targets `data-engineering`. Its integration brings in the #23 catalog,
#38 globe frontend, #16 Region comparison and Mirror support.

## Resolution

- Preserve `WEATHER_REPORT_CATALOG` and the configured catalog from `data/catalog.json`.
- Preserve `getComparison` and `/api/comparison`; retain period-aware `getSeries`
  and all acquisition/cache/fallback behavior.
- Keep the obsolete DiscoveryScreen deleted. Move its intended fallback guard to
  the active MainScreen/DiscoveryPanel rather than restoring an unused screen.
- Preserve the hook's `series` and `notice` interface for the integrated UI, plus
  response-level provenance and the substitution flag.
- Label returned examples by their actual Region, Variable, units and period;
  update globe highlights to those Regions. Suppress the original Discovery
  rates/question and disable investigation when examples substitute the request.
  Keep the direct-investigation guard as well.

## Browser smoke check

Run `.scratch/issue-13-merge/browser-smoke.cjs` with Chromium/Playwright and the
repository dependencies installed. It starts temporary local API/Vite processes
and shuts them down after verification. No NASA request or Earthdata credential
is used. Browser requests are routed to the local API on port 18013.

Verified on 2026-11-14:

1. The #16 Region comparison still renders both charts for a stored pair.
2. A normal Discovery shows two Series with preloaded provenance, sends its
   period in both requests, and enables investigation after data load.
3. Normal investigation still opens Predict.
4. Forcing requests through the actual HTTP fallback returns notices and examples
   with their actual labels/periods, matches globe labels, hides original rates
   and disables the investigation action.
5. At 390 px, fallback has no horizontal overflow after ResizeObserver settles.
6. Direct Become a Detective entry also blocks substituted examples.
7. No browser page errors occurred.

Desktop and mobile screenshots were inspected. The initial immediate resize
assertion failed before the asynchronous canvas resize; waiting for the layout
condition passed without a CSS change. Both results remain in local evidence.

The smoke script, JSON results and screenshots are local session artifacts under
`.scratch/issue-13-merge/`, not committed or remotely hosted. The evidence pack
records their checksums and the final code revision.

Real NASA acquisition remains pending #6. The browser check proves the fallback
and integration behavior, not the live provider.
