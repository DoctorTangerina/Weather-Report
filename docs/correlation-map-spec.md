# Correlation map for independently selected Variables and map areas

## Problem Statement

Users need to investigate how several Earth-science measurements relate, choosing
different Variables within one Selected area, the same Variable across Selected
areas, or different Variables in different Selected areas. They need to assemble
these inputs visually and understand unusable selections without writing code.

## Solution

Deliver the complete frontend, API and data-layer flow. A user selects a rectangle
and multiple Variables, adds those entries, and may repeat with other rectangles.
Each rectangle has an independent Variable selection. For example, temperature
and precipitation from A, soil moisture from B, and temperature and vegetation
index from C become five inputs in one Correlation map. Prepared Derived series
may also participate. Users may remove entries before building.

Users choose a common period and, when necessary, explicit common temporal
resolution and per-input aggregation. The backend returns a numeric Pearson
matrix and metadata, which the frontend renders as a heatmap. Excluded inputs
are removed and explained. This is an exploratory Manual comparison, separate
from automatic Discovery and Mirror generation.

## Stories

### US-001 — Assemble independent selections across map areas

**Type:** User Story

As a user conducting a Manual investigation, I want to select several Variables
for each of several rectangles and add prepared Derived series, so that I can
compare my chosen combinations in one Correlation map.

### US-002 — Choose comparable observations

**Type:** User Story

As a user conducting a Manual investigation, I want a common period and explicit
resampling controls, so that inputs with different frequencies can be compared
without hidden sampling changes.

### US-003 — Read the Correlation map and its explanations

**Type:** User Story

As a user conducting a Manual investigation, I want a labeled heatmap and clear
exclusion and failure explanations, so that I can inspect scores and revise
unusable selections.

### DS-001 — Prepare complete common-timeline inputs

**Type:** Data Story

- **Goal:** Select acquired Source series or prepared Derived series, retain
  source quality and provenance, and explicitly align or aggregate inputs onto
  the requested common output timeline.
- **Source:** Already acquired fields and prepared Derived series, selected by
  area, input identity and common period.
- **Data type:** Numeric observations with timestamps, units, source references,
  geographic bounds and quality/processing metadata.
- **Approximate quantity:** At least two usable inputs for a displayed map;
  there is no fixed input-count limit. Unresolved: expected workload and maximum
  observation volume; no performance target was agreed.

### DS-002 — Return the numeric Correlation map

**Type:** Data Story

- **Goal:** Return exploratory Pearson scores, ordered identities, settings,
  observation count, warnings and exclusion reasons for frontend visualization.
- **Source:** Complete, nonconstant inputs on the common output timeline.
- **Data type:** Symmetric numeric matrix and JSON-compatible metadata.
- **Approximate quantity:** An N-by-N matrix for N retained inputs, with at least
  two observations per input; no fixed input-count cap. Unresolved: expected
  matrix sizes and latency targets.

## Behavioral Specifications

### BS-001 — Build an independently chosen input list

**Stories:** US-001

**Audience:** customer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Correlation input selection
  Users assemble combinations without requiring the same Variables in every Selected area.

Scenario: Adding Variables from another rectangle preserves independent choices
    Given the list contains temperature and precipitation from Selected area A
    And soil moisture is selected for Selected area B
    When the user adds the selection from B
    Then the list contains temperature from A, precipitation from A and soil moisture from B in that order

  Scenario: Adding a prepared Derived series retains its identity
    Given the user has a prepared Derived series called "Scaled temperature A"
    When the user adds it to the input list
    Then the list includes "Scaled temperature A" with its processing history

  Scenario: Adding the exact same input twice does not duplicate it
    Given temperature from Selected area A and dataset X is already in the list
    When the user adds that exact input again
    Then the list still contains only one copy of that input

  Scenario: Removing an input leaves the remaining selections
    Given the list contains inputs A, B and C
    When the user removes B
    Then the list contains A and C in that order

  Scenario Outline: Selected fields support the chosen geographic combination
    Given the user has selected "<selection>" from acquired fields with units, timestamps and source metadata
    When the user adds those selections
    Then every selected input appears with its Variable and Selected area label

    Examples:
      | selection                                                  |
      | temperature and precipitation in area A                     |
      | temperature in areas A and B                                |
      | temperature in area A and soil moisture in area B           |
```

### BS-002 — Require explicit comparable timing

**Stories:** US-002, DS-001

**Audience:** customer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Common analysis settings
  Users decide how sampling frequencies become comparable.

Scenario: Building without a common period requests that period
    Given the input list contains two series
    And no common analysis period is selected
    When the user requests a Correlation map
    Then the interface requires a common analysis period

  Scenario: Matching frequencies retain the existing resolution
    Given two inputs both contain daily observations
    And the user has selected their common analysis period
    When the user builds without requesting resampling
    Then the analysis retains daily resolution

  Scenario: Different frequencies offer explicit resampling or revised selection
    Given one selected input is hourly and another is monthly
    When the user requests a Correlation map without a common resolution
    Then the interface offers explicit common-resolution resampling or revising the selections
    And it does not silently select an aggregation
```

### BS-003 — Resample and align on the chosen output timeline

**Stories:** DS-001, US-002

**Audience:** developer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Common output timeline
  The caller receives comparable observations without implicit repair.

Scenario Outline: Explicit aggregation determines the output bucket value
    Given a selected coarser bucket contains observed values 1, 5 and 9
    When the caller prepares that input with "<aggregation>"
    Then the bucket value is <value>

    Examples:
      | aggregation | value |
      | mean        | 5     |
      | sum         | 15    |
      | minimum     | 1     |
      | maximum     | 9     |
      | median      | 5     |

  Scenario: Nonempty monthly aggregates remain usable despite missing native days
    Given an input passed the acquisition Quality gate
    And every selected month has observed daily values but January lacks one daily observation
    And the resulting monthly means vary
    When the caller prepares monthly means for the common period
    Then the input remains eligible with one aggregate for each selected month
    And no missing daily value is silently filled

  Scenario: Default aggregation boundaries use UTC
    Given inputs need daily aggregation and no shared analysis time zone is selected
    When the caller prepares the common timeline
    Then all daily boundaries use UTC

  Scenario: Explicit time zone controls common bucket boundaries
    Given the selected shared analysis time zone is America/Sao_Paulo
    When the caller prepares daily aggregates
    Then all daily bucket boundaries use America/Sao_Paulo

  Scenario: Nearby observations do not become exact matches
    Given input A has a value at 12:00 UTC and B has a value at 12:05 UTC on the same date
    And no explicit resampling reconciles those instants
    When the caller aligns the inputs
    Then those observations are not treated as matching timestamps
```

### BS-004 — Exclude inputs that cannot form a complete varying sample

**Stories:** DS-001, DS-002

**Audience:** developer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Input eligibility
  Unusable inputs are explained while complete inputs can still be compared.

Scenario Outline: An unusable input is excluded without discarding complete inputs
    Given inputs A and B are complete and nonconstant on the chosen output timeline
    And input C "<condition>"
    When the caller builds the Correlation map
    Then the numeric matrix contains A and B but not C
    And the exclusions identify C with reason "<reason>"

    Examples:
      | condition                                  | reason                         |
      | failed the acquisition Quality gate        | failed acquisition Quality gate |
      | is unavailable in already acquired data    | unavailable input              |
      | lacks one value on the output timeline     | incomplete output timeline     |
      | has an empty month after monthly resampling| incomplete output timeline     |
      | has the same value at every output timestamp | constant input               |

  Scenario: Explicitly filled Derived series retains source provenance
    Given a prepared Derived series has explicitly filled values and a passing source Quality gate assessment
    And it is complete and nonconstant on the chosen timeline
    When the caller builds a map including that input
    Then that input remains eligible with its processing and filled-value provenance
    And the recorded source quality assessment is unchanged
```

### BS-005 — Return calculable Pearson scores and metadata

**Stories:** DS-002

**Audience:** developer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Numeric Correlation map
  The caller receives every retained pair without automatic statistical filtering.

Scenario: A complete sample returns a symmetric ordered matrix
    Given the requested order is B then A
    And their complete values on the three selected monthly timestamps are B equal to 2, 4, 6 and A equal to 1, 2, 3
    When the caller builds the Correlation map
    Then the returned ordered identities are B then A
    And the matrix is [[1, 1], [1, 1]]
    And the result contains input labels, analysis settings, observation count 3, warnings and the excluded-input list

  Scenario: Zero correlation remains a visible numeric result
    Given complete inputs A and B have values 1, 2, 3 and 1, 0, 1 at the three selected timestamps
    When the caller builds the Correlation map
    Then their off-diagonal score is 0
    And neither input is excluded for that score

  Scenario: Two observations produce correlation and a warning
    Given complete inputs A and B have values 1, 2 and 4, 3 at the two selected timestamps
    When the caller builds the Correlation map
    Then their off-diagonal score is -1
    And the result warns that only two observations were used

  Scenario: Exploratory calculation does not apply automatic evidence processing
    Given complete nonconstant inputs from the selected Variables and Selected areas
    When the caller builds their Correlation map
    Then the calculation applies no automatic detrending or seasonal removal
    And no Evidence label or automatic Mirror threshold filters the scores
```

### BS-006 — Visualize scores and explain exclusions

**Stories:** US-003

**Audience:** customer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Correlation heatmap
  Users read the numeric result and understand removed inputs.

Scenario: Selecting a heatmap cell shows the score and both labels
    Given the displayed map has Temperature — Area A and Soil moisture — Area B with correlation 0.4
    When the user selects their comparison cell
    Then the detail shows 0.4, Temperature — Area A and Soil moisture — Area B
    And the heatmap scale remains fixed from -1 to +1

  Scenario: A missing input is removed with a popup and explanation
    Given the request includes complete nonconstant inputs A and B and an input C missing one output observation
    When the user builds the map
    Then the heatmap contains only A and B
    And a popup identifies C and suggests another period or Variable
    And C's exclusion reason appears below the visualization

  Scenario: A constant input is removed and described below the map
    Given inputs A and B are usable and input C is constant
    When the user builds the map
    Then the heatmap contains only A and B
    And text below the map explains that C is constant

  Scenario: Undefined results are hidden and explained separately
    Given a returned comparison is marked undefined rather than having a numeric score
    When the interface displays the result
    Then that comparison has no visualized score and its explanation is listed separately
    And it is not displayed as zero correlation

  Scenario: Two-observation results display their warning
    Given the returned matrix was calculated from two matching observations and includes its warning
    When the interface displays the map
    Then the scores are visible together with the two-observation warning
```

### BS-007 — Explain selection and computation failures

**Stories:** US-003, DS-001

**Audience:** customer-facing

```gherkin
# Source: agreed correlation-map interview and final scope confirmation
Feature: Actionable map failures
  Users can revise unsupported or unusable requests.

Scenario Outline: Too few retained inputs require revised selection
    Given exclusions leave <count> usable inputs
    When the user builds the map
    Then no empty or single-cell heatmap is displayed
    And the interface shows the exclusions and requests revised selections

    Examples:
      | count |
      | 0     |
      | 1     |

  Scenario: An unsupported rectangle requests redrawing
    Given the selected rectangle crosses the antimeridian
    When the user requests data for it
    Then the interface explains that the rectangle is unsupported and asks the user to redraw
    And the rectangle is not silently changed

  Scenario: Unavailable coverage explains the selected area
    Given acquired data do not cover a selected rectangle
    When the user requests data for it
    Then the interface explains the unavailable coverage and allows redrawing

  Scenario: Resource failure asks the user to reduce inputs
    Given computation fails because the selected request exceeds available resources
    When the interface receives that failure
    Then it asks the user to reduce the number of inputs
    And no partial computation is presented as the complete requested matrix
```

## Implementation Decisions

- Include frontend selection and visualization, API integration and reusable
  numeric methods in the data layer. This feature has broader ownership than
  the earlier data-only processing work.
- Use existing acquired-data selection and its acquisition Quality gate; do
  not trigger NASA downloads. Support ordinary bounding boxes initially.
- Keep Selected areas distinct from catalog Regions. Selections are independent
  per rectangle and geographic origin does not restrict comparisons.
- Preserve order, stable input IDs, source metadata and Derived-series history.
  Disambiguate labels with dataset/Derived-series names when necessary.
- Accept a common period and resolution, plus explicit per-input aggregation.
  Reuse processing operations without automatic filling, upsampling or nearest
  matching. Common aggregation time zone defaults to UTC. Respect confirmed
  local zones of already prepared filters.
- Assess completeness on the chosen output timeline, after explicit resampling.
  Nonempty buckets may use incomplete native observations; empty output buckets
  exclude the input. Keep acquisition quality distinct from output completeness.
- Exclude missing, unavailable, acquisition-rejected and constant inputs with
  explanations, retaining comparisons among the remaining eligible inputs.
- Return ordered IDs/labels, symmetric numeric scores with unit diagonal,
  analysis settings, observation count, warnings and excluded-input reasons.
  Keep undefined results outside numeric visualization rather than using zero.
- Calculate Pearson with at least two complete varying observations. Warn at
  two; do not impose an evidence/significance threshold or reject weak scores.
  This intentionally differs from the three-pair minimum in #51. Share numerical
  infrastructure where useful without changing either interface's behavior.
- Use a labeled heatmap with fixed -1 to +1 scale, score/input-label cell details,
  exclusion text below, missing-data popup and two-observation warning.
- Do not impose a configured input-count limit. Resource failures instruct users
  to reduce inputs; do not silently truncate the request.
- Respect the accepted deterministic Discovery methodology and statistical ADRs;
  automatic Mirror/Trend/Evidence behavior remains unchanged.

## Testing Decisions

The user confirmed these seams in Q32 and confirmed the complete scope afterward:

- **S1 — Public data-processing method:** supply selected inputs and common
  analysis settings, observe numeric results, exclusions, warnings and provenance.
  Verify BS-003, BS-004 and BS-005 here with deterministic acquired/Derived fixtures.
- **S2 — Public API integration:** pass selection descriptors and analysis settings
  through the API into real data-layer processing with deterministic local fixtures.
  Verify transport of BS-003, BS-004 and BS-005 outputs and the result/failure states
  consumed by BS-006 and BS-007. Endpoint names and transport error codes are not
  prescribed by this spec.
- **S3 — Frontend user flow:** verify BS-001, BS-002, BS-006 and BS-007 through
  selection, request, loading, heatmap and explanation behavior, with controlled
  service responses for resource and unavailable-data cases.
- Prefer these existing public boundaries; do not add private-helper seams.
  Assert values, identities/order, settings, labels, exclusions, preservation of
  source history and visible states rather than internal calls or component structure.
- Prior art includes acquired-series/Quality gate fixture tests, existing public
  API comparison tests using deterministic Series, and frontend formatting tests.
  Extend user-flow coverage as necessary; existing formatting tests alone cannot
  establish selection/heatmap behavior.
- Do not require Earthdata credentials or live NASA downloads for verification.
  The existing automatic engine suite guards its unchanged behavior; these are
  new agreed behaviors, not regression BS entries for a refactor.

## Out of Scope

- New dataset acquisition or NASA download integrations.
- Polygon selection and antimeridian-crossing boxes.
- Automatic Discovery, Mirror, Trend or Evidence-methodology changes.
- Statistical-significance filtering or automatic suppression of weak scores.
- Automatic filling, nearest-timestamp matching, manufactured finer sampling,
  detrending, seasonal removal, lag analysis or time shifting.
- Building additional hour/day/season filters: sampling here means frequency.
  Prepared Derived series may already contain explicit processing choices.
- Fixed selection-count caps.

## Further Notes

- Related processing parent: #46; explicit resampling/alignment: #48; exploratory
  Pearson infrastructure: #51. These are reuse/integration points, not a blanket
  dependency on all seven processing tickets.
- The final scope explicitly includes different Variables from different rectangles
  in the same matrix, without requiring a shared Variable list across rectangles.
- Unresolved: expected observation volume, latency, deployment resource envelope,
  and operational timeout/cancellation policy. No numeric targets are invented.
- Unresolved: exact endpoint/type names. Reuse the existing resampling contract
  for calendar boundaries and acquisition conventions for provider no-data values;
  this spec adds no invented transport codes or quality thresholds.
- Fewer than two observations cannot produce Pearson; the user explicitly allowed
  mathematically calculable results from two observations. No score should be
  fabricated for an undefined calculation.
- Local documentation includes the agreed interview record, this specification
  and its BDD quality-gate review. No new ADR is necessary for this feature.
