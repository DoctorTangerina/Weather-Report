# Issue #15: investigation and evidence

## Final browser recheck — PASS (2026-11-14)

The final sidebar version was subsequently checked with individual Edge/CDP
interactions. Predict has no charts/evidence, and Continue is disabled until a
prediction is selected. Selected option and Continue have computed background
rgb(6, 80, 107) and white text; the alternate option remains transparent. Check
shows both charts, correct and incorrect predictions show their respective
feedback, and timeline playback advanced both charts from 2000-01 to 2000-02.
Reason labels all three causes as context and disables timeline playback. Evidence
is available in Discovery/Check/Reason. Back restores Discovery, re-entry clears
the prediction, and the same MainScreen and globe canvas persist throughout.
Mobile Check was inspected at 390px: page/sidebar widths were 390px, with readable
charts and no horizontal overflow. No product source changes were needed.

Timestamped raw results, mobile screenshot and follow-up evidence pack are in
`.scratch/_evidence/issue-15-final-browser.jsonl`, `issue-15-final-mobile.png` and
`issue-15-final-browser-recheck.md`. PASS covers UI smoke with supplied stub data;
it does not establish real NASA provenance or automated UI coverage. The older
walkthrough and previously pending checks below are retained as history.

The Predict → Check → Reason investigation now replaces only the sidebar content
on MainScreen. The globe stays mounted, with the same selected Regions. Back returns
the sidebar to the Discovery; a successful Surprise Me! also returns it to the
Discovery summary. During Check, the existing timeline controls the comparison
charts. During Predict and Reason, playback is disabled and no charts are shown.
The evidence panel
is shared by the Discovery sidebar and the Check and Reason investigation steps;
it is hidden during Predict. Possible
causes explicitly state that they are scientific context and are not established
by the displayed data. Prediction options and match/mismatch wording remain those
already supplied by the stub contract and existing UI; the ticket leaves their
final editorial design open.

## Verification (2026-11-14)

- `npm.cmd run build`: passed; Vite reports the existing large globe bundle warning.
- Existing full suite: 30 passed using temporary pytest/jsonschema/httpx packages
  under `.scratch/smoke-deps`. The suite reports a Starlette/httpx deprecation warning.
- `git diff --check`: passed.
- No typechecking script is configured in this JavaScript frontend.
- No automated UI tests were added, as requested by the issue.

Before the subsequent sidebar integration, the browser walkthrough used individual CDP commands against a separate headless Edge
instance, with the stub API on port 8000 and Vite on port 5173. This verifies DOM
content and interactions; it is not a visual layout review.
The sidebar integration was validated by a fresh production build and diff check;
the browser walkthrough below has not been repeated against that integration.

Observed on the Amazon Basin / Sahel Discovery:

- Opened How do we know? directly from the Discovery. It showed Strong evidence,
  the 2000-01 to 2024-12 period, per-decade rates and 95% intervals, Region and
  Variable names, synthetic source attribution, intended NASA provider and method
  citation supplied by the API.
- Opened Become a Detective: Predict showed both Region options, no charts, and
  a disabled Check the data button before selecting a prediction.
- Selected Sahel and continued: Check showed two charts and “Your guess matches
  the computed Trends.” The comparison included the two rates and intervals.
- Continued to Reason: all three causes had Context from scientists labels, with
  the explicit statement that the data do not establish causes. Opened the evidence
  panel there and confirmed the same rates, period, source and citation.

## Repeat and remaining checks

Start the API and frontend using the repository README. Select Surprise Me!, open
How do we know?, then Become a Detective. Select either Region and Check the data,
then Why might this happen? Repeat with the other Region to inspect mismatch
feedback. Confirm each cause says Context from scientists and the surrounding
copy says the data do not establish causes. Confirm evidence is absent during
Predict. Open evidence during Check and Reason and verify
the period, both Region rates and intervals, Evidence labels, source and citation.
Check keyboard interaction and narrow-screen layout visually.
Also confirm the globe canvas remains the same DOM element when entering and
leaving the investigation, that no chart is shown during Predict, and that timeline
playback updates both charts during Check.

The committed fixtures contain synthetic observations, unresolved NASA dataset
metadata and an incomplete method citation. The UI reports the supplied source
honestly; real source metadata and a complete paper reference remain upstream
data work. No commit, push or tracker publication was performed for this change.
