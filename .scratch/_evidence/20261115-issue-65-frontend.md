# Evidence Pack

- **Pack ID:** issue-65-frontend-f1f77ee
- **Template version:** 1.0
- **Generated at (UTC):** 2026-11-15T16:17:18Z (regenerated; verification results reused)
- **Overall status:** PASS (frontend claims); publication unavailable
- **Task mode:** github
- **Task reference:** DoctorTangerina/Weather-Report#65, frontend only
- **Repository:** C:/Users/ADM/Documents/Weather-Report
- **Branch:** feat/65-frontend-fixes
- **Base revision:** 595a4dc438f437933f5c0dff549a445a313dfbe6
- **Current revision:** f1f77ee726586a93a389da3aad5a5e62c9e2db71
- **Working-tree state:** tracked files clean; untracked .scratch/ contains this recovery pack
- **Producer:** Codex

## 1. Executive result

Frontend changes remove initial Region selection, preserve globe highlights and
layout during Discovery loading, and make Become a Detective honor a selected
pair. Seven Chromium tests and four unit tests pass; the production build passes.
Local Earth textures were already present and their serving was verified.
GitHub CLI has no authentication, preventing evidence publication. The backend
and data portions of #65 remain outside the user-authorized scope.
The branch and revision were rechecked at 2026-11-15T16:17:18Z and still match
the verified implementation. No new commit or push was performed for this
evidence request; the implementation commit predates the user's instruction
to withhold further commits and pushes.

## 2. Scope-to-proof map

| Claim ID | Requirement or property | Source | Verification | Evidence IDs | Status |
| --- | --- | --- | --- | --- | --- |
| CLM-001 | No initially selected Regions or automatic comparison | #65 frontend | Chromium welcome test, then manual pair selection and charts | EVD-001 | PASS |
| CLM-002 | Stable globe through Discovery and investigation transitions | #65 frontend | Same canvas, dimensions, retained labels, no browser errors | EVD-001, EVD-004 | PASS |
| CLM-003 | Textures served with app without external network | #65 frontend | External requests blocked, local texture responses successful; production copies match SHA-256 | EVD-001, EVD-005 | PASS |
| CLM-004 | Automated investigation happy path | #65 verification | Surprise Me! → Become a Detective → Check → How do we know? | EVD-001 | PASS |
| CLM-005 | Detective honors chosen pair and explains unavailable/incomplete selections | User follow-up | Three Chromium tests use pair differing from random endpoint; no random request on selected-pair path | EVD-001 | PASS |

## 3. Change inventory

- **Added:** Playwright config, seven browser tests, frontend smoke documentation.
- **Modified:** App selection routing, MainScreen selection/loading state, Explorer placeholders, Globe memoization, frontend dependencies/scripts, frontend test-output ignores.
- **Deleted:** None.
- **Config/schema changes:** Playwright dev dependency and test:e2e script; no API/schema changes.
- **Externally visible behaviour changes:** Empty welcome selection, stable loading globe, selected-pair investigation.
- **Intentionally untouched:** API, engine, seed data, README, Python lint, bundle splitting.

## 4. Verification bundle

- **Tests run:** Four existing unit tests and seven browser tests.
- **Newly added tests:** Welcome/manual selection; direct detective; selected-pair detective; no Discovery; incomplete pair; investigation happy path/globe stability; local textures.
- **Edge/failure cases covered:** No Discovery retains selection; one Region asks for another; external texture hosts blocked.
- **Integration/e2e checks:** Real React/WebGL frontend, existing catalog/seed HTTP fixtures, Chromium.
- **Skipped or unavailable checks:** Live API/NASA integration; manual visual review; Python suite unavailable; no typecheck script. No BS scenarios in this issue, so BDD scenario review is NOT_APPLICABLE.

Commands below ran during implementation at this file content; exact individual UTC run times were not captured. Results collected at the pack timestamp. Frontend working directory is C:/Users/ADM/Documents/Weather-Report/frontend; root commands use its parent.

| Command | Exit code | Result | Evidence ID |
| --- | --- | --- | --- |
| npx playwright test --workers=1 (frontend) | 0 | 7 passed; 36.1 s | EVD-001 |
| npm test (frontend) | 0 | 4 passed | EVD-002 |
| npm run build (frontend) | 0 | Production bundle built; existing large-chunk warning | EVD-003 |
| npx playwright test -g 'keeps the globe' --workers=1, temporary highlight-clearing mutation (frontend) | 1 test process | Label-loss assertion failed as intended; source restored in finally; wrapper exited 0 | EVD-004 |
| Get-FileHash on source and dist texture pairs (root) | 0 hash operation | Source/build hashes match for both textures | EVD-005 |
| python -m pytest -q (root) | 1 | Active Python environment has no pytest | EVD-006 |
| git -c safe.directory=C:/Users/ADM/Documents/Weather-Report diff HEAD~1 HEAD --check (root) | 0 diff operation | No whitespace errors | EVD-007 |
| gh issue view 65 --repo DoctorTangerina/Weather-Report --comments --json comments (root) | 1 | No GitHub CLI authentication; idempotency query unavailable | EVD-008 |
| gh issue view 65 --repo DoctorTangerina/Weather-Report --comments --json comments (root), 2026-11-15T16:17:18Z | 1 | Regeneration publication preflight still fails: no authentication | EVD-009 |
| gh issue comment 65 --repo DoctorTangerina/Weather-Report --body-file .scratch/_evidence/20261115-issue-65-frontend.md (root) | 1 | Publication failed: gh auth login or GH_TOKEN required | EVD-010 |

## 5. Engineering hygiene

| Category | Status | Evidence ID |
| --- | --- | --- |
| Linting | NOT_RUN | Python files untouched |
| Formatting | NOT_RUN | EVD-007 is whitespace checking only |
| Static analysis | NOT_RUN | None run |
| Type checking | NOT_RUN | No configured frontend typecheck |
| Build | PASS | EVD-003 |
| Repo-specific architectural rules / coding standards | PARTIAL | Test-first failures observed for selection, label clearing, resizing and selected-pair routing; mutation killed; Python suite unavailable |

## 6. Plan ledger and deviations

- **Conceptual plan:** Implement #65 frontend only with browser regression coverage.
- **Executed approach:** Remove selection defaults; retain drawing highlights and timeline; stabilize globe inputs; verify bundled textures; add browser tests; commit.
- **Deviations:** User follow-up added selected-pair detective routing using existing GET /api/discoveries; remains frontend only. No texture asset change needed. API live smoke replaced with deterministic frontend smoke; explicitly limited scope.

## 7. Rationale and trade-offs

- **Approach taken:** Reuse engine-authored Discovery narratives and existing API, selecting an exact Region pair in the frontend.
- **Alternatives considered:** Random draw despite selection; creating investigation content client-side.
- **Why rejected:** Changes user selection or invents scientific content.
- **Known trade-offs:** Fetches existing Discovery catalog for selected-pair entry. Its lead Contrast determines the investigation Variable. No Discovery for a pair produces an explanation.

## 8. Exploration archive

Initial welcome test failed on amazon-basin being preselected. Transition tests
observed lost labels and canvas height changing 825 → 924 during loading.
Selected-pair test failed because the random endpoint returned a different pair.
All pass after fixes. Browser setup initially lacked Chromium; installed it.
Sandbox Vite access failed; authorized elevated runs succeeded. Dependency install
reported two audit findings (one moderate, one high); no dependency remediation attempted.

## 9. Risks, rollback, and limitations

- **Residual risk / blast radius:** Frontend only; visual smoothness is represented by DOM/layout/canvas invariants, not pixel-level animation assessment.
- **Rollback approach:** Revert f1f77ee.
- **Incomplete work:** Non-frontend #65 criteria remain open; evidence publication needs GitHub authentication.
- **Assumptions:** Investigations use existing Discovery lead Contrasts; free exploration does not generate new Discoveries.
- **Environment limitations:** No authenticated gh; active Python lacks pytest.
- **Missing evidence:** No live NASA smoke or manual visual browser review; no typecheck/lint run.
- **Follow-up work:** Complete backend/data/hygiene criteria separately; publish this pack after authentication is restored.

## 10. Chain of custody

Producer for all artifacts: Codex. Repository, branch and revision are recorded
above; results were collected at 2026-11-15T16:11:22Z. EVD-001/002/003/004/006 are
terminal results in the implementation session, not persisted raw logs. EVD-007
and EVD-008 were collected after commit. No fabricated per-run timestamps.
EVD-009 was collected at 2026-11-15T16:17:18Z on the unchanged branch revision.
EVD-010 followed regeneration; its exact UTC execution time was not captured.

Test source: frontend/e2e/discovery.spec.js, SHA-256
408B533E90E1390CFAF8EA4A36E184EA9F420BC8AC994E00806620BEA2A39F46.

Texture SHA-256, identical in public/textures and dist/textures:
- earth-blue-marble.jpg: 228DEBA2E4B600146BDCB6CFA359B8EAD6AACC2B1C13550A29CD82824CFA1C01
- earth-topology.png: 839B12DA2E4DD346B256CEBAE72E10C479A102C8980A22084C41275E4B9A0E12

## 11. Machine-readable manifest

<!-- evidence-manifest:start -->

```yaml
manifest_version: "1.0"
pack_id: "issue-65-frontend-f1f77ee"
task:
  mode: "github"
  reference: "DoctorTangerina/Weather-Report#65"
repository:
  branch: "feat/65-frontend-fixes"
  base_revision: "595a4dc438f437933f5c0dff549a445a313dfbe6"
  current_revision: "f1f77ee726586a93a389da3aad5a5e62c9e2db71"
generated:
  at_utc: "2026-11-15T16:17:18Z"
  producer: "Codex"
claims:
  - { id: CLM-001, status: PASS, evidence_ids: [EVD-001] }
  - { id: CLM-002, status: PASS, evidence_ids: [EVD-001, EVD-004] }
  - { id: CLM-003, status: PASS, evidence_ids: [EVD-001, EVD-005] }
  - { id: CLM-004, status: PASS, evidence_ids: [EVD-001] }
  - { id: CLM-005, status: PASS, evidence_ids: [EVD-001] }
artifacts:
  - id: EVD-001
    category: test
    status: PASS
    claim_ids: [CLM-001, CLM-002, CLM-003, CLM-004, CLM-005]
    command: "npx playwright test --workers=1"
    working_directory: "C:/Users/ADM/Documents/Weather-Report/frontend"
    exit_code: 0
    pointer: "Implementation session; frontend/e2e/discovery.spec.js"
    sha256: "408B533E90E1390CFAF8EA4A36E184EA9F420BC8AC994E00806620BEA2A39F46"
    generated_at_utc: "individual run time not captured; collected 2026-11-15T16:11:22Z"
    producer: Codex
    tool: Playwright
  - { id: EVD-002, category: test, status: PASS, command: "npm test", exit_code: 0 }
  - { id: EVD-003, category: build, status: PASS, command: "npm run build", exit_code: 0 }
  - { id: EVD-004, category: test, status: PASS, command: "temporary highlight-clearing mutation; targeted Playwright test", exit_code: 1 }
  - { id: EVD-005, category: other, status: PASS, command: "Get-FileHash source/build texture pairs", exit_code: 0 }
  - { id: EVD-006, category: test, status: NOT_RUN, command: "python -m pytest -q", exit_code: 1 }
  - { id: EVD-007, category: diff, status: PASS, command: "git diff HEAD~1 HEAD --check", exit_code: 0 }
  - { id: EVD-008, category: other, status: FAIL, command: "gh issue view 65 --comments --json comments", exit_code: 1 }
  - { id: EVD-009, category: other, status: FAIL, command: "gh issue view 65 --repo DoctorTangerina/Weather-Report --comments --json comments", exit_code: 1, generated_at_utc: "2026-11-15T16:17:18Z" }
  - { id: EVD-010, category: other, status: FAIL, command: "gh issue comment 65 --repo DoctorTangerina/Weather-Report --body-file .scratch/_evidence/20261115-issue-65-frontend.md", exit_code: 1 }
```

<!-- evidence-manifest:end -->

<!-- evidence-pack:DoctorTangerina/Weather-Report#65:f1f77ee726586a93a389da3aad5a5e62c9e2db71 -->
