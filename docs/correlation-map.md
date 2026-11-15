# Correlation map — feature interview

Published specification: [GitHub issue #56](https://github.com/DoctorTangerina/Weather-Report/issues/56).
Local specification: [correlation-map-spec.md](correlation-map-spec.md).
Scenario review: [correlation-map-bdd-review.md](correlation-map-bdd-review.md).

## Implementation sub-issues

- [#60 — Build and inspect independent area selections](https://github.com/DoctorTangerina/Weather-Report/issues/60): no blockers.
- [#61 — Explain excluded inputs and request failures](https://github.com/DoctorTangerina/Weather-Report/issues/61): blocked by #60.
- [#62 — Resample selected inputs to a common timeline](https://github.com/DoctorTangerina/Weather-Report/issues/62): blocked by #60 and existing #48.

All three are native sub-issues of #56 with native blocking relationships.

## Requested outcome

The user constructs a list in the frontend. Each entry identifies a Variable and
an area selected on the map. The list may contain different Variables in one
area, one Variable across different areas, or different Variables across
different areas. Data-layer processing returns numeric correlation results for
later visualization. This work includes documentation and a GitHub issue once
the feature's behavior is agreed; it does not yet authorize implementation.

## Agreed decisions

- Q1: A Correlation map is a pairwise correlation matrix, not a geographic field.
- Q2: Selected areas are rectangular bounding boxes, distinct from catalog Regions.
- Q3: This feature includes frontend selection and visualization, API integration,
  and numeric processing in the data layer.
- Q4: Both Source series and Derived series may participate, preserving source
  and processing history.
- Q5: Use exploratory Pearson correlation, reusing Manual comparison rules from
  #51, without automatic detrending, seasonal removal or Evidence labels.
- Q6: One common analysis period applies to the matrix; Derived series retain
  their history and contribute observations within that period.
- Q7: Use already acquired data only. Unavailable selections are explained so
  users can change them; new NASA acquisition is outside this feature.
- Q8: Offer all available acquired fields with the required units, timestamps
  and source metadata, plus Derived series. Use readable labels and dataset
  names to distinguish sources where needed.
- Q10: Inputs use one shared period and resolution, aligned by matching
  timestamps; equal row counts alone do not establish comparability.
- Q11: Remove unavailable or Quality-gate-excluded inputs from the matrix and
  report why each was excluded.
- Q13: Hide undefined correlations in the visualization and report them
  separately. Selecting a valid cell shows the correlation score and the two
  Variable names. No sample-count detail panel is required by this decision.
- Q9 clarification: Do not silently calculate on a reduced pairwise sample when
  a selected input lacks observations on the shared timeline. Show a popup
  identifying the input and suggesting another period or Variable. The exact
  completeness rule and whether remaining inputs proceed still need confirmation.
- Q12 clarification: Do not reject a mathematically computable correlation
  merely because the chosen series is uninformative. Distinguish this from
  mathematically undefined Pearson correlation for constant inputs.

- Q14: Any missing observation on the shared analysis timeline excludes that
  input. Show a popup identifying missing data and suggesting a different period
  or Variable; continue with the remaining complete inputs. Users may explicitly
  prepare filled inputs through the separate processing feature.
- Q15: Remove constant inputs from the matrix and describe their exclusion in
  text below the visualization; never manufacture numeric Pearson values.
- Q16: Allow two or more matching observations when both inputs vary. With
  exactly two observations, return the calculable score and show a warning.
  This intentionally differs from #51's three-observation minimum. Do not reject
  weak or zero correlation or add automatic significance/Evidence thresholds.
- Q17: Let users explicitly choose a common coarser resolution and per-input
  aggregation, reusing the processing feature. Check completeness after
  aggregation; never fill automatically.
- Q18: Select a rectangle and multiple Variables, then add all entries. Users
  can select another rectangle or proceed with their list, choose resolution,
  period and sampling pattern as needed, then build. Prepared Derived series may
  be added and list entries removed. Sampling pattern needs clarification.
- Final clarification: Variable choices are independent per rectangle. One map
  may combine temperature and precipitation from rectangle A, soil moisture
  from rectangle B, and temperature and vegetation index from rectangle C.
  There is no requirement that rectangles use the same Variables.
- Q19: Preserve input-list order, prevent exact duplicate inputs, and label
  entries by Variable and Selected area, adding dataset or Derived-series names
  where needed to distinguish sources.
- Q20: If fewer than two usable inputs remain, show explanations and request
  revised selections rather than displaying an empty or single-cell matrix.
- Q21: “Sampling pattern” means temporal frequency, not a request for hour/day/
  season filters in this feature. For hourly versus monthly inputs, offer
  explicit hourly-to-monthly resampling or let users revise their selections so
  they have the same sampling units.
- Q22: A monthly aggregate may be displayed despite missing underlying daily
  observations. Completeness is assessed on the selected output timeline, not
  by requiring every native observation inside a nonempty aggregate bucket.
  Do not impose the rejected complete-native-bucket requirement.
- Q23: Use one shared analysis time zone, default UTC, for aggregation and
  alignment. If local-time filters are supplied through prepared processing,
  use confirmed per-input time zones according to that feature's rules.
- Q24: Return ordered IDs and labels, a symmetric numeric matrix with diagonal
  1 for retained inputs, analysis settings, observation count, warnings and a
  separate excluded-input list with reasons.
- Q25: No configured maximum number of selected series. Do not invent a limit;
  engineering behavior for computational failures still needs definition.
- Q26: Any empty output bucket excludes its input. Explain the missing period
  and offer another period, resolution or Variable.
- Q27: Source selections must pass the existing acquisition Quality gate before
  resampling. The map additionally checks completeness at the output resolution.
- Q28: Display a heatmap on a fixed -1 to +1 scale. A selected cell shows score
  and both input labels; exclusion descriptions appear below the visualization.
  Missing-data exclusions also trigger a popup; two-observation results warn.
- Q29: On computational/resource failure, tell users to reduce the number of
  inputs. No fixed selection cap is introduced, and no partial computation is
  silently presented as the complete requested result.
- Q30: Require a common period. Keep the existing frequency when inputs match;
  otherwise require explicit common resolution and aggregation choices.
- Q31: Initially use ordinary rectangular boxes supported by existing selection.
  Explain unsupported antimeridian-crossing boxes or unavailable coverage and
  let users redraw; never silently change their selection.
- Q32: Verify numeric behavior through the public data method, API integration
  with deterministic fixtures, and frontend list/heatmap/exclusion flows.
  Verification does not require live NASA downloads.

## Interview status

All interview questions are resolved. The user confirmed the complete scope,
including independent Variable selections per rectangle, and requested to-spec.
The confirmed verification boundaries are the public numeric method, API
integration and frontend flow.

## Integration notes

- #46 and its child tickets provide processing concepts and operations. #48
  supplies explicit resampling and alignment. Source selection already supports
  ordinary bounding boxes and applies the acquisition Quality gate.
- #51 specifies at least three valid pairs for its Manual comparison. This
  Correlation map intentionally permits two complete varying observations with
  a warning. Reuse numerical infrastructure where suitable without silently
  changing either public behavior.
- Automatic Mirror processing, thresholds and Evidence labels are unchanged.
- The new feature includes API and frontend implementation as well as numeric
  processing in the data folder.

The existing manual-processing feature is issue #46. Its API and frontend are
separately owned, and manual results do not feed automatic Discovery generation.
The present feature explicitly includes frontend and API work; the earlier
feature's ownership boundary does not limit this feature.
