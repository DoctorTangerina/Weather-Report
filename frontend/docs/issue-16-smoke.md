# Issue #16 browser smoke test

Executed on 2026-11-14 against the local API and Vite frontend with the committed
synthetic data. Browser actions used Playwright with installed Brave Chromium;
desktop and mobile screenshots were also inspected visually.

To repeat, start the API and frontend as described in the root README and open
http://127.0.0.1:5173/.

1. On the welcome screen, choose Amazon Basin and Sahel. Confirm both selectors
   contain only catalog Regions and exclude the Region selected in the other.
   Confirm two Trend cards show computed rates, 95% intervals and Evidence labels,
   followed by two charts matching the Regions' colors on the globe.
2. Choose precipitation. Confirm both charts change to mm/month. Choose Central
   India as the second Region and switch back to temperature. Confirm both charts
   show K and the second Trend/card names Central India. This pair has no stored
   Discovery, so the result exercises analysis of the selected series.
3. Choose Congo Basin. Confirm the unavailable-data alert appears and the previous
   pair's charts and Trend cards disappear. Choose Sahel again and confirm recovery.
4. Inspect at 1440 × 1000 and 390 × 844. Confirm both charts remain present on mobile
   with no horizontal overflow. The desktop sidebar scrolls to reach the charts.
5. Click Surprise Me! and confirm a Discovery and its two charts still appear.

All steps passed. No browser JavaScript exceptions were observed. The first default
pair includes Congo Basin, which currently has no bundled series and therefore
shows the unavailable-data message until a supported pair is selected.

Automated verification: 150 Python tests passed, including eight new HTTP seam
tests; four existing frontend tests passed; production build, Python type checking,
Ruff lint and format checks passed. Both temporary mutations (omitting Evidence
rating and reversing chart series order) were detected by the new HTTP test.
Each mutation ran inside `try/finally`, which restored and byte-checked the original
file even when the test returned failure.

Limitations: these checks use synthetic data, not NASA acquisition. Vite reports
the existing large globe bundle warning; pytest reports the existing Starlette/
httpx deprecation warning. There is no configured frontend typecheck script.
