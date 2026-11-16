# Evidence Pack

- **Pack ID:** issue-106-8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4
- **Template version:** 1.0
- **Generated at (UTC):** 2026-11-15T23:33:15.728959Z
- **Overall status:** PARTIAL
- **Task mode:** github
- **Task reference:** #106 ? https://github.com/DoctorTangerina/Weather-Report/issues/106
- **Repository:** DoctorTangerina/Weather-Report
- **Branch:** frontend
- **Base revision:** 8659a51e2efc9a89094bf387f770201dd1843d55 (comparison baseline is current HEAD, including merged #80)
- **Current revision:** 8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4 (HEAD plus actual uncommitted patch checksum)
- **Working-tree state:** dirty; staged and unstaged frontend implementation changes. Index is not assumed to equal tested working files. Nothing committed or pushed by this evidence task.
- **Producer:** Codex

## 1. Executive result

Explore My World requests a debounced timeline period over a permanent full-span axis, with one set of chart settings, English controls, handle-following labels, centered timestamp and a fixed-height error row. Final implementation observations show 18 browser tests, 18 unit tests and the build passing; an earlier real-API Time-step run passed 11 tests.

**Evidence is PARTIAL, not a blanket completion certificate:** the full integration suite has a known stale seed-data assertion tracked in [#108](https://github.com/DoctorTangerina/Weather-Report/issues/108), and the area/job/Aggregation suites were not all rerun after the final layout iteration. This pack identifies uncommitted working files, not a published commit. Original test command UTC execution times were not captured; collection UTC and available file times are labeled separately.

## 2. Scope-to-proof map

| Claim ID | Requirement or property | Source | Verification | Evidence IDs | Status |
| -------- | ------------------------ | ------ | ------------- | ------------ | ------ |
| CLM-001 | No Period fieldset; timeline is the only period selector. | #106 AC1 | components/ExploreMyWorld.jsx; ExploreTimeline.jsx; EVD-001 checks no native month inputs/Period fieldset. | EVD-001, EVD-010 | PASS |
| CLM-002 | Whole requestable span from 2000-01 through latest month before and after loading. | #106 AC2; final user correction | ExploreTimeline domain; EVD-001 endpoints remain 2000-01..2025-02 while request pending and after completion. | EVD-001, EVD-010 | PASS |
| CLM-003 | Debounced range requests; opening defaults stay seed span for Region and last 12 months for Selected area. | #106 AC3 | useExploreSeries 300 ms timeout; useExploreView default diff unchanged; final browser request parameters and earlier Selected-area default assertions. | EVD-001, EVD-005, EVD-009, EVD-010 | PASS |
| CLM-004 | Time-step caps refused before requests, with same message beside timeline. | #106 AC4 / BS-002 reference | EVD-001 exact boundary and no-request checks; EVD-004 real-API cap tests. | EVD-001, EVD-004 | PASS |
| CLM-005 | One Aggregation, Time step and period applies to all charts. | #106 AC5 / BS-002 reference | Combined request hook; real API time-step rebuilding both Variables; earlier maximum Aggregation checks. | EVD-004, EVD-007, EVD-010 | PASS |
| CLM-006 | Discovery, Investigation and two-Region compare retain client-side range filtering. | #106 AC6 | Final browser inclusive slicing/playback tests and all three view label-stability/navigation tests; only Explore receives controlled request domain. | EVD-001, EVD-010 | PASS |
| CLM-007 | E2E and Explore/Selected-area/job integration tests migrated to timeline control; verification is clean across suites. | #106 AC7; verification expectation | Diff confirms migration; final browser and Time-step integration pass. Other suites passed earlier, but full integration has known stale assertion #108 and was not rerun on final layout. | EVD-001, EVD-004, EVD-005, EVD-006, EVD-007, EVD-008, EVD-010 | PARTIAL |
| CLM-008 | UI stays English under Portuguese browser locale; no duplicate native date/Time-step sidebar controls. | User corrections after #106 | Final e2e test.use locale pt-BR, no month inputs and only Aggregation select; English From/To labels. | EVD-001 | PASS |
| CLM-009 | Compact Time-step choices remain in heading; full span marks selected period and fits desktop/mobile height. | Final user corrections | 1440/390 px browser geometry; heading alignment, full-span endpoints and footer height bound. | EVD-001, EVD-013, EVD-014 | PASS |
| CLM-010 | From/To track handles; timestamp centered; error sits right of speed controls without growing height. | Latest user correction | Final e2e geometry verifies label centers at range positions, timestamp centered, error beside speed group and exact unchanged footer height. | EVD-001, EVD-013, EVD-014, EVD-015, EVD-016 | PASS |

Issue #106 contains no Behavioral Specifications section or supplied Gherkin. Its references to BS-002 are traced above without inventing a scenario body or story IDs. No formal regression-BS base/current suite claim is added.

## 3. Change inventory

- **Added:** frontend/src/components/ExploreTimeline.jsx; frontend/e2e/explore-timeline.spec.js.
- **Modified:** Timeline, MainScreen, ExploreMyWorld, useExploreView, useExploreSeries, styles; Explore/areas/jobs/Aggregations/Time-step integration tests.
- **Deleted:** no files; duplicate sidebar Period and Time-step controls removed.
- **Config/schema changes:** real-API Playwright wait limits increased for worker acquisition; no response schema change.
- **Externally visible behaviour changes:** timeline-only period selection drives requests; full-span highlight; compact heading choices; labels follow handles; timestamp centered; errors reuse footer row rather than growing it; English even under pt-BR browser locale.
- **Intentionally untouched:** backend acquisition, engine calculations, committed seed files and Discovery selection. Existing #80 Time-step behavior preserved. Complete changed-file inventory and hashes: EVD-010/EVD-011.

## 4. Verification bundle

- **Tests run:** reused recorded results from implementation; no expensive browser rerun solely for this evidence pack.
- **Newly added tests:** two viewport cases (1440 and 390 px) in explore-timeline.spec.js, under pt-BR locale.
- **Edge/failure cases covered:** no Series yet; no intermediate request before debounce; inclusive cap limits and refusal without requests; excluded/unavailable Variables and jobs in earlier real-API runs; backend failure text; cap error must not add height; narrow labels track the selected range.
- **Integration/e2e checks:** final 18-browser run; earlier 11 Time-step, 7 area, 2 job and 2 Aggregation runs, with chronology retained rather than portrayed as one final all-suite run.
- **Skipped or unavailable checks:** no final complete real-API integration rerun; no base browser run; no authenticated NASA calls, deploy, Python full suite, lint/formatter/type checker. Prior raw command logs and exact execution UTC were not saved. Screenshots and current patch are preserved locally, not uploaded as attachments.

| Command | Exit code | Result | Evidence ID |
| ------- | --------- | ------ | ------------ |
| `npm run test:e2e -- --workers=1 --timeout=90000` | 0 | 18 passed (1.5m). Final desktop/mobile test covers full span before/after load, debounce, exact cap boundaries, English under pt-BR locale, moving labels, centered timestamp, compact header and error placement without height growth. | EVD-001 |
| `npm test; git -c safe.directory=C:/Users/ADM/Documents/Weather-Report diff --check` | 0 | 18 unit tests passed; no whitespace errors. Tests include caps, UTC stepping and inclusive range slicing. | EVD-002 |
| `npm run build` | 0 | 183 modules transformed; production build succeeded in 6.09s. Existing large-chunk warning remains. | EVD-003 |
| `npm run test:time-steps` | 0 | 11 real-API tests passed (1.2m): all three Time steps, computed daily values/precipitation totals, caps without requests, UTC explanations, Variable removal, progress and failed-fetch reporting. Run after full-span migration, before final label/error-position CSS changes. | EVD-004 |
| `npm run test:areas` | 0 | 7 passed (43.0s) in an earlier UI iteration, including Selected-area 12-month opening period and Quality gate exclusions. Not rerun in full after the final layout changes. | EVD-005 |
| `npm run test:integration -- --config playwright.jobs.config.js` | 0 | 2 passed (53.3s) in an earlier UI iteration: background acquisition, cached repeat and failure reporting. Not rerun after final full-span migration/layout. | EVD-006 |
| `npm run test:integration -- --config playwright.aggregations.config.js` | 0 | 2 passed (1.4m) in an earlier UI iteration: seven Aggregations and rebuilding all charts using maximum. Not rerun after final full-span migration/layout. | EVD-007 |
| `npm run test:integration` | 1 | 6 passed; 1 failed: Variables without data are not offered, and Back returns to welcome expected 3 Amazon Basin checkboxes, received 4. Seed contains vegetation-index. Subsequently tracked independently in issue #108. No clean full-suite pass is claimed. | EVD-008 |
| `npm run test:e2e -- e2e/explore-timeline.spec.js --workers=1` | 1 | Expected mutation failure: temporarily disabling debounce produced 2 requests where 1 was required. Restored to 300 ms; later complete browser run passed. | EVD-009 |
| `git -c safe.directory=C:/Users/ADM/Documents/Weather-Report diff HEAD --binary -- .` | 0 | Actual dirty-tree patch captured against HEAD; default Region/Selected-area periods remain unchanged, stable Explore timeline key omits period/Variables; only Explore uses the controlled request domain. | EVD-010 |
| `Python pathlib/hashlib source snapshot` | 0 | SHA-256 hashes and actual last-write UTC for all 15 changed frontend files; current HEAD and working-tree revision recorded. | EVD-011 |
| `bdd-scenarios review-mode applicability inspection` | None | No in-scope Gherkin or Behavioral Specifications section in #106. All eight review attributes NOT_APPLICABLE; no scenarios invented. Reference to BS-002 alone is not a scenario body. | EVD-012 |

Negative evidence and earlier failed experiments: EVD-017. Reused command summaries are not raw stdout; their generation timestamps identify evidence collection. EVD-012 records BDD review applicability, with all eight attributes NOT_APPLICABLE because no in-scope Gherkin exists.

## 5. Engineering hygiene

| Category | Status | Evidence ID |
| --- | --- | --- |
| Linting | NOT_RUN | EVD-017 |
| Formatting | NOT_RUN | EVD-017 |
| Static analysis | NOT_RUN | EVD-017 |
| Type checking | NOT_RUN | EVD-017 |
| Build | PASS | EVD-003 |
| Repo-specific architectural rules / coding standards | PARTIAL | EVD-002, EVD-009, EVD-010, EVD-017 |

Whitespace check and debounce mutation were observed; no broader coding-standards review is claimed.

## 6. Plan ledger and deviations

- **Conceptual plan:** replace the Period fieldset with a request-driving timeline; preserve defaults/caps and client filtering in other views; verify existing integration flows.
- **Executed approach:** controlled Explore-only timeline domain/range, a 300 ms request debounce with cleanup, stable per-place key, heading Time-step controls and existing API acquisition/jobs.
- **Deviations:** user first selected rescaling, then explicitly reversed that decision to full-span highlighting; final implementation follows the last decision. User requested no commit/push and compact controls, English UI, centered timestamp and errors beside speed without growth; all retained. #80 merged during the work, so duplicate sidebar controls were removed again while preserving its Time-step logic. Evidence remains scoped to the current dirty patch on top of #107, not earlier branch HEADs.

## 7. Rationale and trade-offs

- **Approach taken:** request again for changed periods so server-side Quality gate semantics use that requested period; keep other experiences on their client-only filter path.
- **Alternatives considered:** client-only slicing in Explore; rescaling plus a restore-full-period control; sidebar month inputs.
- **Why rejected:** client-only slicing would judge a different period; the user superseded rescaling and removed extra controls; native month inputs showed OS/browser-localized month names.
- **Known trade-offs:** 300 ms coalesces keyboard/drag steps; labels are vertically staggered within the existing track area for narrow selections. During a cap error, the endpoint metadata row is replaced by the accessible message to preserve height. Production bundle still emits the pre-existing large-chunk warning.

## 8. Exploration archive

EVD-017 retains the red runs, debounce mutation, timing-dependent checks, rescaling/playhead experiment, stale server 404 diagnosis and pre-#80 501 behavior. These are historical observations, not current product failures unless separately marked. No speculative scenario was created to manufacture evidence.

## 9. Risks, rollback, and limitations

- **Residual risk / blast radius:** shared Timeline markup/styles affect all views; final navigation/playback/filtering browser cases passed. Full real-API integration still lacks a clean pass due #108.
- **Rollback approach:** review/apply the inverse of EVD-010 selectively in an isolated copy; do not reset this shared working tree or discard concurrent work. No rollback command was executed.
- **Incomplete work:** stale availability fixture assertion remains; not closed by this pack.
- **Assumptions:** latest requestable month and Time-step availability are supplied by the API; no NASA service-access claim is made from synthetic-grid tests.
- **Environment limitations:** Windows PowerShell, network sandbox retries and initial GitHub authentication failures are retained in negative evidence. Previous stale local server lacked Explore routes despite checkout definitions.
- **Missing evidence:** original raw stdout, exact run UTC and source checksums taken at each prior run; final all-integration pass; base suite; linter/type checker and real NASA validation.
- **Follow-up work:** address #108 and verify the full integration suite on the eventual committed revision. Regenerate this pack when working files or HEAD change.

## 10. Chain of custody

All artifact generation timestamps below are collection UTC unless an actual file modification time is separately recorded. Reused tests point to conversation tool chunks; summaries are explicitly marked. No checksum is claimed for unpersisted original stdout. Current source snapshot and patch hashes are computed over real files. The final browser test deliberately mocks a 501 response for error presentation; this does not describe the current backend capability (the real-API Time-step suite passed). Local recovery directory: `C:\Users\ADM\Documents\Weather-Report\frontend\.scratch\_evidence\20261115T233030-issue-106`.

- **EVD-001**: Codex; artifact file UTC 2026-11-15T23:32:30.034206Z; test / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-001-observed-summary.txt`; SHA-256 `2794ad589f7674887faf93595fb15c41bf276f1f349671990334b534fef417d4`.
- **EVD-002**: Codex; artifact file UTC 2026-11-15T23:32:30.040228Z; test / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-002-observed-summary.txt`; SHA-256 `7a9fd2bba2835a70c7cc430e9c290176d918bf9f321d59056440d9fceb8ea0ed`.
- **EVD-003**: Codex; artifact file UTC 2026-11-15T23:32:30.044228Z; build / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-003-observed-summary.txt`; SHA-256 `08c67931467e35823258433fd7bcc4a45f5f3d6a453a2a89e71665c825ee2eb3`.
- **EVD-004**: Codex; artifact file UTC 2026-11-15T23:32:30.049246Z; test / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-004-observed-summary.txt`; SHA-256 `de79b67412317c2412dcde9a917b9a7a213dca6391c2ba8f8eda002aa0ac714a`.
- **EVD-005**: Codex; artifact file UTC 2026-11-15T23:32:30.054247Z; test / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-005-observed-summary.txt`; SHA-256 `947ac4ec6e2385e456f015d03f5929ed892b6be4d6224175767de63dd9042aa3`.
- **EVD-006**: Codex; artifact file UTC 2026-11-15T23:32:30.059266Z; test / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-006-observed-summary.txt`; SHA-256 `dbbf87af81013113a9bb282a1524f7ba87bd3813d7b693e1193b9446420b7812`.
- **EVD-007**: Codex; artifact file UTC 2026-11-15T23:32:30.064265Z; test / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-007-observed-summary.txt`; SHA-256 `40a8ae7d519723268e56a817e2368afee2f43445b81dace3097e22a6befe12a9`.
- **EVD-008**: Codex; artifact file UTC 2026-11-15T23:32:30.070859Z; test / FAIL; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-008-observed-summary.txt`; SHA-256 `087ab1bc479a805d1304a8f98549cf7ea3488fea5515ec8733e7f3252d06dd78`.
- **EVD-009**: Codex; artifact file UTC 2026-11-15T23:32:30.075866Z; test / FAIL; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\EVD-009-observed-summary.txt`; SHA-256 `39df9cab73ab947641a75ef2718ef87124581a2461b3e4474c98c91ce1d45c77`.
- **EVD-010**: Codex; artifact file UTC 2026-11-15T23:30:30.895753Z; diff / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\worktree.patch`; SHA-256 `e7c3c67f0cfa80f42f836492cfec63f3e8c539d1a65ee2facc3e0d039dbcc357`.
- **EVD-011**: Codex; artifact file UTC 2026-11-15T23:30:30.982003Z; other / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\source-snapshot.json`; SHA-256 `525851e1a7092799efc463201ddeccaeb4b708e4da21a9cd053917bad8f1d1c1`.
- **EVD-012**: Codex; artifact file UTC 2026-11-15T23:30:31.016737Z; decision / NOT_APPLICABLE; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\bdd-review.md`; SHA-256 `17842f2f823c57c5133a8065b72099b0bf3b0af5104a2d696903d104ae0d6fdf`.
- **EVD-013**: Codex; artifact file UTC 2026-11-15T23:23:04.391012Z; other / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\explore-timeline-1440.png`; SHA-256 `809033625988cb83012b5d8d8847e1a895e625664bb444424931de27e3aef937`.
- **EVD-014**: Codex; artifact file UTC 2026-11-15T23:23:11.520455Z; other / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\explore-timeline-390.png`; SHA-256 `651abff7454645bd8324bd81261b57cd4b0707a0d22352508644bb8791921049`.
- **EVD-015**: Codex; artifact file UTC 2026-11-15T23:23:04.557150Z; other / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\explore-timeline-error-1440.png`; SHA-256 `95aaa38819146bb18414d8f4c891a51749bc2b3d52f7f3a27245114861d4cac8`.
- **EVD-016**: Codex; artifact file UTC 2026-11-15T23:23:11.671566Z; other / PASS; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\explore-timeline-error-390.png`; SHA-256 `6ea6648b1270818ef5654719ecab6710e6085403d3be835192206c7f3f1f6fc4`.
- **EVD-017**: Codex; artifact file UTC 2026-11-15T23:32:30.110931Z; risk / PARTIAL; command and working directory in manifest; repo DoctorTangerina/Weather-Report, branch frontend, revision `8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4`; local pointer `.scratch\_evidence\20261115T233030-issue-106\negative-evidence.md`; SHA-256 `df2843352a272033bce7ea644a511803b4ff9a3db962d8e20edc49748b2ceeff`.

## 11. Machine-readable manifest

<!-- evidence-manifest:start -->

```yaml
{
  "manifest_version": "1.0",
  "pack_id": "issue-106-8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
  "task": {
    "mode": "github",
    "reference": "#106"
  },
  "repository": {
    "name": "DoctorTangerina/Weather-Report",
    "branch": "frontend",
    "base_revision": "8659a51e2efc9a89094bf387f770201dd1843d55",
    "current_revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4"
  },
  "generated": {
    "at_utc": "2026-11-15T23:33:15.728959Z",
    "producer": "Codex"
  },
  "claims": [
    {
      "id": "CLM-001",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-010"
      ]
    },
    {
      "id": "CLM-002",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-010"
      ]
    },
    {
      "id": "CLM-003",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-005",
        "EVD-009",
        "EVD-010"
      ]
    },
    {
      "id": "CLM-004",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-004"
      ]
    },
    {
      "id": "CLM-005",
      "status": "PASS",
      "evidence_ids": [
        "EVD-004",
        "EVD-007",
        "EVD-010"
      ]
    },
    {
      "id": "CLM-006",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-010"
      ]
    },
    {
      "id": "CLM-007",
      "status": "PARTIAL",
      "evidence_ids": [
        "EVD-001",
        "EVD-004",
        "EVD-005",
        "EVD-006",
        "EVD-007",
        "EVD-008",
        "EVD-010"
      ]
    },
    {
      "id": "CLM-008",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001"
      ]
    },
    {
      "id": "CLM-009",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-013",
        "EVD-014"
      ]
    },
    {
      "id": "CLM-010",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-013",
        "EVD-014",
        "EVD-015",
        "EVD-016"
      ]
    }
  ],
  "artifacts": [
    {
      "id": "EVD-001",
      "category": "test",
      "status": "PASS",
      "claim_ids": [
        "CLM-001",
        "CLM-002",
        "CLM-003",
        "CLM-004",
        "CLM-006",
        "CLM-008",
        "CLM-009",
        "CLM-010"
      ],
      "command": "npm run test:e2e -- --workers=1 --timeout=90000",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "18 passed (1.5m). Final desktop/mobile test covers full span before/after load, debounce, exact cap boundaries, English under pt-BR locale, moving labels, centered timestamp, compact header and error placement without height growth.",
      "generated_at_utc": "2026-11-15T23:32:30.034206Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-001-observed-summary.txt",
      "sha256": "2794ad589f7674887faf93595fb15c41bf276f1f349671990334b534fef417d4",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-002",
      "category": "test",
      "status": "PASS",
      "claim_ids": [],
      "command": "npm test; git -c safe.directory=C:/Users/ADM/Documents/Weather-Report diff --check",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "18 unit tests passed; no whitespace errors. Tests include caps, UTC stepping and inclusive range slicing.",
      "generated_at_utc": "2026-11-15T23:32:30.040228Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-002-observed-summary.txt",
      "sha256": "7a9fd2bba2835a70c7cc430e9c290176d918bf9f321d59056440d9fceb8ea0ed",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-003",
      "category": "build",
      "status": "PASS",
      "claim_ids": [],
      "command": "npm run build",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "183 modules transformed; production build succeeded in 6.09s. Existing large-chunk warning remains.",
      "generated_at_utc": "2026-11-15T23:32:30.044228Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-003-observed-summary.txt",
      "sha256": "08c67931467e35823258433fd7bcc4a45f5f3d6a453a2a89e71665c825ee2eb3",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-004",
      "category": "test",
      "status": "PASS",
      "claim_ids": [
        "CLM-004",
        "CLM-005",
        "CLM-007"
      ],
      "command": "npm run test:time-steps",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "11 real-API tests passed (1.2m): all three Time steps, computed daily values/precipitation totals, caps without requests, UTC explanations, Variable removal, progress and failed-fetch reporting. Run after full-span migration, before final label/error-position CSS changes.",
      "generated_at_utc": "2026-11-15T23:32:30.049246Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-004-observed-summary.txt",
      "sha256": "de79b67412317c2412dcde9a917b9a7a213dca6391c2ba8f8eda002aa0ac714a",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-005",
      "category": "test",
      "status": "PASS",
      "claim_ids": [
        "CLM-003",
        "CLM-007"
      ],
      "command": "npm run test:areas",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "7 passed (43.0s) in an earlier UI iteration, including Selected-area 12-month opening period and Quality gate exclusions. Not rerun in full after the final layout changes.",
      "generated_at_utc": "2026-11-15T23:32:30.054247Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-005-observed-summary.txt",
      "sha256": "947ac4ec6e2385e456f015d03f5929ed892b6be4d6224175767de63dd9042aa3",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-006",
      "category": "test",
      "status": "PASS",
      "claim_ids": [
        "CLM-007"
      ],
      "command": "npm run test:integration -- --config playwright.jobs.config.js",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "2 passed (53.3s) in an earlier UI iteration: background acquisition, cached repeat and failure reporting. Not rerun after final full-span migration/layout.",
      "generated_at_utc": "2026-11-15T23:32:30.059266Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-006-observed-summary.txt",
      "sha256": "dbbf87af81013113a9bb282a1524f7ba87bd3813d7b693e1193b9446420b7812",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-007",
      "category": "test",
      "status": "PASS",
      "claim_ids": [
        "CLM-005",
        "CLM-007"
      ],
      "command": "npm run test:integration -- --config playwright.aggregations.config.js",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "2 passed (1.4m) in an earlier UI iteration: seven Aggregations and rebuilding all charts using maximum. Not rerun after final full-span migration/layout.",
      "generated_at_utc": "2026-11-15T23:32:30.064265Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-007-observed-summary.txt",
      "sha256": "40a8ae7d519723268e56a817e2368afee2f43445b81dace3097e22a6befe12a9",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-008",
      "category": "test",
      "status": "FAIL",
      "claim_ids": [
        "CLM-007"
      ],
      "command": "npm run test:integration",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 1,
      "result": "6 passed; 1 failed: Variables without data are not offered, and Back returns to welcome expected 3 Amazon Basin checkboxes, received 4. Seed contains vegetation-index. Subsequently tracked independently in issue #108. No clean full-suite pass is claimed.",
      "generated_at_utc": "2026-11-15T23:32:30.070859Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-008-observed-summary.txt",
      "sha256": "087ab1bc479a805d1304a8f98549cf7ea3488fea5515ec8733e7f3252d06dd78",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-009",
      "category": "test",
      "status": "FAIL",
      "claim_ids": [
        "CLM-003"
      ],
      "command": "npm run test:e2e -- e2e/explore-timeline.spec.js --workers=1",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 1,
      "result": "Expected mutation failure: temporarily disabling debounce produced 2 requests where 1 was required. Restored to 300 ms; later complete browser run passed.",
      "generated_at_utc": "2026-11-15T23:32:30.075866Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "original_run_at_utc": null,
      "timestamp_note": "Artifact generation UTC is the observed summary file modification UTC, not original command execution UTC; original run time was not recorded.",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\EVD-009-observed-summary.txt",
      "sha256": "39df9cab73ab947641a75ef2718ef87124581a2461b3e4474c98c91ce1d45c77",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-010",
      "category": "diff",
      "status": "PASS",
      "claim_ids": [
        "CLM-001",
        "CLM-002",
        "CLM-003",
        "CLM-005",
        "CLM-006",
        "CLM-007"
      ],
      "command": "git -c safe.directory=C:/Users/ADM/Documents/Weather-Report diff HEAD --binary -- .",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "Actual dirty-tree patch captured against HEAD; default Region/Selected-area periods remain unchanged, stable Explore timeline key omits period/Variables; only Explore uses the controlled request domain.",
      "generated_at_utc": "2026-11-15T23:30:30.895753Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\worktree.patch",
      "sha256": "e7c3c67f0cfa80f42f836492cfec63f3e8c539d1a65ee2facc3e0d039dbcc357",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-011",
      "category": "other",
      "status": "PASS",
      "claim_ids": [],
      "command": "Python pathlib/hashlib source snapshot",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "SHA-256 hashes and actual last-write UTC for all 15 changed frontend files; current HEAD and working-tree revision recorded.",
      "generated_at_utc": "2026-11-15T23:30:30.982003Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\source-snapshot.json",
      "sha256": "525851e1a7092799efc463201ddeccaeb4b708e4da21a9cd053917bad8f1d1c1",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-012",
      "category": "decision",
      "status": "NOT_APPLICABLE",
      "claim_ids": [],
      "command": "bdd-scenarios review-mode applicability inspection",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": null,
      "result": "No in-scope Gherkin or Behavioral Specifications section in #106. All eight review attributes NOT_APPLICABLE; no scenarios invented. Reference to BS-002 alone is not a scenario body.",
      "generated_at_utc": "2026-11-15T23:30:31.016737Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\bdd-review.md",
      "sha256": "17842f2f823c57c5133a8065b72099b0bf3b0af5104a2d696903d104ae0d6fdf",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-013",
      "category": "other",
      "status": "PASS",
      "claim_ids": [
        "CLM-009",
        "CLM-010"
      ],
      "command": "Playwright timeline locator screenshot in EVD-001",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "Real screenshot from final successful browser run; file retained locally. Generation time below is collection time; actual file modification time retained by copy2.",
      "generated_at_utc": "2026-11-15T23:23:04.391012Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\explore-timeline-1440.png",
      "sha256": "809033625988cb83012b5d8d8847e1a895e625664bb444424931de27e3aef937",
      "file_modified_at_utc": "2026-11-15T23:23:04.391012+00:00",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-014",
      "category": "other",
      "status": "PASS",
      "claim_ids": [
        "CLM-009",
        "CLM-010"
      ],
      "command": "Playwright timeline locator screenshot in EVD-001",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "Real screenshot from final successful browser run; file retained locally. Generation time below is collection time; actual file modification time retained by copy2.",
      "generated_at_utc": "2026-11-15T23:23:11.520455Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\explore-timeline-390.png",
      "sha256": "651abff7454645bd8324bd81261b57cd4b0707a0d22352508644bb8791921049",
      "file_modified_at_utc": "2026-11-15T23:23:11.520455+00:00",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-015",
      "category": "other",
      "status": "PASS",
      "claim_ids": [
        "CLM-009",
        "CLM-010"
      ],
      "command": "Playwright timeline locator screenshot in EVD-001",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "Real screenshot from final successful browser run; file retained locally. Generation time below is collection time; actual file modification time retained by copy2.",
      "generated_at_utc": "2026-11-15T23:23:04.557150Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\explore-timeline-error-1440.png",
      "sha256": "95aaa38819146bb18414d8f4c891a51749bc2b3d52f7f3a27245114861d4cac8",
      "file_modified_at_utc": "2026-11-15T23:23:04.557150+00:00",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-016",
      "category": "other",
      "status": "PASS",
      "claim_ids": [
        "CLM-009",
        "CLM-010"
      ],
      "command": "Playwright timeline locator screenshot in EVD-001",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": 0,
      "result": "Real screenshot from final successful browser run; file retained locally. Generation time below is collection time; actual file modification time retained by copy2.",
      "generated_at_utc": "2026-11-15T23:23:11.671566Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\explore-timeline-error-390.png",
      "sha256": "6ea6648b1270818ef5654719ecab6710e6085403d3be835192206c7f3f1f6fc4",
      "file_modified_at_utc": "2026-11-15T23:23:11.671566+00:00",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    },
    {
      "id": "EVD-017",
      "category": "risk",
      "status": "PARTIAL",
      "claim_ids": [],
      "command": "Conversation/tool result audit",
      "working_directory": "C:\\Users\\ADM\\Documents\\Weather-Report\\frontend",
      "exit_code": null,
      "result": "Chronological failures, superseded limitations, missing checks and timestamp limitations retained.",
      "generated_at_utc": "2026-11-15T23:32:30.110931Z",
      "producer": "Codex",
      "tool": "functions.exec / exec_command",
      "tool_version": "not captured",
      "repository": "DoctorTangerina/Weather-Report",
      "branch": "frontend",
      "revision": "8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4",
      "pointer": ".scratch\\_evidence\\20261115T233030-issue-106\\negative-evidence.md",
      "sha256": "df2843352a272033bce7ea644a511803b4ff9a3db962d8e20edc49748b2ceeff",
      "collection_started_at_utc": "2026-11-15T23:30:30.811087Z"
    }
  ]
}
```

<!-- evidence-manifest:end -->

<!-- evidence-pack:#106:8659a51e2efc9a89094bf387f770201dd1843d55+worktree-e7c3c67f0cfa80f4 -->
