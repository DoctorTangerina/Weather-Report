# Evidence Pack

- **Pack ID:** issue-15-final-browser-recheck-20261114T214739Z
- **Template version:** 1.0
- **Generated at (UTC):** 2026-11-14T21:47:39.2337941Z
- **Overall status:** PASS
- **Task mode:** github
- **Task reference:** DoctorTangerina/Weather-Report#15
- **Repository:** C:/Users/ADM/Documents/Weather-Report
- **Branch:** front/detective
- **Base revision:** a1d38358ae9ed6de8ecb8d94dd177b4b450446ba
- **Current revision:** a1d38358ae9ed6de8ecb8d94dd177b4b450446ba-working-tree (not a new Git commit)
- **Working-tree state:** dirty, intentionally uncommitted under user's instruction.
- **Producer:** Codex

## 1. Executive result

PASS for the requested final UI smoke with stub data. The previously unverified sidebar, globe retention, timeline coupling, filled prediction buttons, evidence visibility and incorrect-prediction path were exercised in the final browser version. No product source changes were needed.

This follow-up supersedes the manual UI verification gaps in 20261114T213739Z-issue-15.md; the earlier pack is retained as history. Publication remains blocked by the previously observed GitHub CLI authentication failure. PASS is confined to the UI/stub scope: it does not assert real NASA provenance, a complete bibliographic reference or automated UI coverage.

## 2. Scope-to-proof map

| Claim ID | Requirement or property | Source | Verification | Evidence IDs | Status |
| -------- | ------------------------ | ------ | ------------- | ------------ | ------ |
| CLM-001 | Prediction precedes charts (BS-006 / US-002) | Issue #15 or subsequent user instruction | No automated UI test by issue decision | — | NOT_APPLICABLE |
| CLM-002 | Comparison displays charts and prediction feedback (BS-006 / US-002) | Issue #15 or subsequent user instruction | No automated UI test by issue decision | — | NOT_APPLICABLE |
| CLM-003 | Causes labeled as scientific context (BS-006 / US-002) | Issue #15 or subsequent user instruction | No automated UI test by issue decision | — | NOT_APPLICABLE |
| CLM-004 | Discovery provenance fields (BS-008 / US-003) | Issue #15 or subsequent user instruction | No automated UI test by issue decision | — | NOT_APPLICABLE |
| CLM-005 | Final manual browser smoke covers Predict, Check and Reason | Issue #15 or subsequent user instruction | Individual CDP interactions; zero charts/no evidence/disabled Continue initially; correct and incorrect feedback; three cause labels | EVD-008 | PASS |
| CLM-006 | Investigation stays in sidebar; Back restores Discovery; globe preserved | Issue #15 or subsequent user instruction | MainScreen and canvas object identity true across entering, Check, Reason and Back; restart clears selection | EVD-008 | PASS |
| CLM-007 | Selected prediction and Check the data visibly filled | Issue #15 or subsequent user instruction | Computed background rgb(6,80,107), white foreground; alternate option transparent; Continue enabled after selection | EVD-008 | PASS |
| CLM-008 | Evidence absent in Predict and available in Check/Reason | Issue #15 or subsequent user instruction | Final DOM observations: no details in Predict; evidence readable in Check/Reason; restart resets Predict | EVD-008 | PASS |
| CLM-009 | Evidence renders supplied stub source and trust fields honestly | Issue #15 or subsequent user instruction | Final Check panel shows 2000-01–2024-12, per-decade rates, 95% intervals, labels, supplied method citation, synthetic attribution and intended NASA provider | EVD-008 | PASS |
| CLM-010 | Timeline controls both comparison charts | Issue #15 or subsequent user instruction | Playback advances 2000-01 to 2000-02; both values use 2000-02; playback disabled in Predict and Reason | EVD-008 | PASS |
| CLM-011 | Mobile comparison fits screen | Issue #15 or subsequent user instruction | 390px viewport/page/sidebar; retained screenshot visually inspected, two charts readable and timeline visible | EVD-008, EVD-009 | PASS |
| CLM-012 | Build and existing backend suite passed | Issue #15 or subsequent user instruction | Reused final production build and 30-test suite from implementation; no product source changed during recheck | EVD-001, EVD-002 | PASS |

BS-derived automated claims remain NOT_APPLICABLE under the issue's explicit manual-smoke/no-automated-UI-test decision. The separate manual claim is PASS; no automated test EVD is attached to BS rows.

## 3. Change inventory

- **Added:** final-browser JSONL, mobile screenshot and this follow-up pack.
- **Modified:** smoke notes receive a final-verification addendum.
- **Deleted:** no tracked product files.
- **Config/schema changes:** none.
- **Externally visible behaviour changes:** none during this recheck; verifies existing uncommitted issue #15 changes.
- **Intentionally untouched:** all product source and backend logic.

## 4. Verification bundle

- **Tests run:** individual browser smoke actions against local Vite :5173 and healthy stub API :8000. Reused prior final build and existing full backend suite; no rerun needed without source changes.
- **Newly added tests:** none. Temporary CDP helper is an inspection aid, not an installed UI test suite.
- **Edge/failure cases covered:** no initial guess, matching/mismatching predictions, restarting after Back, disabled playback outside Check, synthetic attribution.
- **Integration/e2e checks:** same MainScreen/canvas DOM objects; sidebar content switches; timeline advances both displayed values from January to February 2000; final evidence visibility checked.
- **Skipped or unavailable checks:** exhaustive keyboard/accessibility audit, every Discovery combination, real NASA data and final full paper citation are outside this limited smoke. GitHub publication unavailable.

| Command | Exit code | Result | Evidence ID |
| ------- | --------- | ------ | ------------ |
| node .scratch/recheck-cdp.mjs with individual expressions, retained verbatim in JSONL action fields | 0 for successful inspections | Final Predict/Check/Reason, correct/incorrect feedback, Back/reset, colors, evidence and timeline confirmed | EVD-008 |
| node .scratch/recheck-cdp.mjs mobile-shot | 0 | Emulation and screenshot in same CDP session: viewport/page/sidebar 390px, two charts; screenshot inspected using view_image | EVD-009 |
| npm.cmd run build | 0 (reused) | 167 modules, 20.56s; existing bundle-size advisory | EVD-001, previous pack |
| full pytest command recorded in previous pack | 0 (reused) | 30 passed, one deprecation warning; backend-only coverage | EVD-002, previous pack |
| git -c safe.directory=C:/Users/ADM/Documents/Weather-Report diff --check | 0 | No whitespace errors; LF/CRLF advisory | current conversation 93fee3 |
| bdd-scenarios review mode | N/A (reused) | Review and title revisions retained in issue-15-bdd-review.md; no source behavior changed | EVD-005, previous pack |

Negative evidence retained in JSONL: one initial expression used top-level await and returned a SyntaxError; corrected async expression then returned the expected observations. An initial mobile-emulation command disconnected before measurement, so the next session reverted to its default viewport; that measurement/screenshot was not used as mobile proof. Repeated emulation, measurement and screenshot in one session yielded 390px correctly. No product defect was inferred from either inspection-tool issue.

## 5. Engineering hygiene

| Category | Status | Evidence ID |
| --- | --- | --- |
| Linting | NOT_RUN | — |
| Formatting | PARTIAL | diff --check only; not a formatter run |
| Static analysis | NOT_RUN | — |
| Type checking | NOT_RUN | — |
| Build | PASS | EVD-001 reused |
| Repo-specific architectural rules / coding standards | NOT_RUN | — |

The overall PASS refers to UI smoke claims, not to skipped hygiene categories.

## 6. Plan ledger and deviations

- **Conceptual plan:** recheck the specific UI gaps behind PARTIAL and report the observed result.
- **Executed approach:** final-browser walkthrough, computed style checks, DOM identity checks, real timeline playback, both prediction outcomes, mobile screenshot.
- **Deviations:** corrected two inspection-tool mistakes described above. No product changes, commit, push or external write.

## 7. Rationale and trade-offs

- **Approach taken:** retain raw timestamped results and screenshot, reuse valid build/test results.
- **Alternatives considered:** automated UI tests or rerunning unchanged backend suite.
- **Why rejected:** issue calls for manual smoke; backend suite does not prove these UI behaviors.
- **Known trade-offs:** focused smoke coverage, no claim of exhaustive UI or scientific validation.

## 8. Exploration archive

The browser helper invoked separate inspection actions. The transcript preserves successful results and tool errors rather than discarding inconvenient observations. Source-file hashes in issue-15-provenance.json describe the implementation snapshot; recheck did not modify those source files.

## 9. Risks, rollback, and limitations

- **Residual risk / blast radius:** unexercised catalog combinations and detailed keyboard/accessibility behavior.
- **Rollback approach:** no product changes made by this verification; earlier implementation diff remains available.
- **Incomplete work:** upstream NASA dataset metadata and complete method reference remain placeholders; they are explicitly represented as stub data.
- **Assumptions:** ticket #15's stub-data scope, existing prediction options/wording.
- **Environment limitations:** headless Edge; GitHub CLI authentication unavailable in prior preflight.
- **Missing evidence:** no automated BS test, by ticket instruction; no publication receipt.
- **Follow-up work:** authenticate GitHub CLI before publishing; check idempotency marker before writing.

## 10. Chain of custody

Producer Codex, branch front/detective, HEAD a1d38358ae9ed6de8ecb8d94dd177b4b450446ba plus unchanged implementation working tree. Browser record timestamps and exact expressions are in JSONL; working directory C:/Users/ADM/Documents/Weather-Report/frontend. SHA-256 hashes actually computed:

- issue-15-final-browser.jsonl: 4182E46B3ADD077ED0A647A2FFA7B6EF3748D03D9EF8E710EE65C1C269E12395
- issue-15-final-mobile.png: 05A2585D83CFB2CF079CC8AF31AA0EFEDBAE5CBDF95B0CF116903B9A5DB3766F

Earlier artifact details and hashes remain in 20261114T213739Z-issue-15.md. EVD-001/002/005 references are inherited from that pack, not newly generated evidence.

## 11. Machine-readable manifest

<!-- evidence-manifest:start -->

```yaml
{
  "manifest_version": "1.0",
  "pack_id": "issue-15-final-browser-recheck-20261114T214739Z",
  "task": {
    "mode": "github",
    "reference": "DoctorTangerina/Weather-Report#15"
  },
  "repository": {
    "branch": "front/detective",
    "base_revision": "a1d38358ae9ed6de8ecb8d94dd177b4b450446ba",
    "current_revision": "a1d38358ae9ed6de8ecb8d94dd177b4b450446ba-working-tree"
  },
  "generated": {
    "at_utc": "2026-11-14T21:47:39.2337941Z",
    "producer": "Codex"
  },
  "claims": [
    {
      "id": "CLM-001",
      "status": "NOT_APPLICABLE",
      "evidence_ids": []
    },
    {
      "id": "CLM-002",
      "status": "NOT_APPLICABLE",
      "evidence_ids": []
    },
    {
      "id": "CLM-003",
      "status": "NOT_APPLICABLE",
      "evidence_ids": []
    },
    {
      "id": "CLM-004",
      "status": "NOT_APPLICABLE",
      "evidence_ids": []
    },
    {
      "id": "CLM-005",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008"
      ]
    },
    {
      "id": "CLM-006",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008"
      ]
    },
    {
      "id": "CLM-007",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008"
      ]
    },
    {
      "id": "CLM-008",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008"
      ]
    },
    {
      "id": "CLM-009",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008"
      ]
    },
    {
      "id": "CLM-010",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008"
      ]
    },
    {
      "id": "CLM-011",
      "status": "PASS",
      "evidence_ids": [
        "EVD-008",
        "EVD-009"
      ]
    },
    {
      "id": "CLM-012",
      "status": "PASS",
      "evidence_ids": [
        "EVD-001",
        "EVD-002"
      ]
    }
  ],
  "artifacts": [
    {
      "id": "EVD-008",
      "category": "other",
      "status": "PASS",
      "claim_ids": [
        "CLM-005",
        "CLM-006",
        "CLM-007",
        "CLM-008",
        "CLM-009",
        "CLM-010",
        "CLM-011"
      ],
      "command": "node .scratch/recheck-cdp.mjs <individual expression or mode>; exact expressions and UTC results retained in JSONL",
      "working_directory": "C:/Users/ADM/Documents/Weather-Report/frontend",
      "exit_code": 0,
      "pointer": "issue-15-final-browser.jsonl",
      "sha256": "4182E46B3ADD077ED0A647A2FFA7B6EF3748D03D9EF8E710EE65C1C269E12395",
      "generated_at_utc": "Per-record UTC timestamps in JSONL",
      "producer": "Codex",
      "tool": "Node/CDP/Edge"
    },
    {
      "id": "EVD-009",
      "category": "other",
      "status": "PASS",
      "claim_ids": [
        "CLM-011"
      ],
      "command": "node .scratch/recheck-cdp.mjs mobile-shot; view_image",
      "working_directory": "C:/Users/ADM/Documents/Weather-Report/frontend",
      "exit_code": 0,
      "pointer": "issue-15-final-mobile.png",
      "sha256": "05A2585D83CFB2CF079CC8AF31AA0EFEDBAE5CBDF95B0CF116903B9A5DB3766F",
      "generated_at_utc": null,
      "producer": "Codex",
      "tool": "Edge/CDP, view_image"
    }
  ]
}
```

<!-- evidence-manifest:end -->

<!-- evidence-pack:DoctorTangerina/Weather-Report#15:a1d38358ae9ed6de8ecb8d94dd177b4b450446ba-working-tree -->

