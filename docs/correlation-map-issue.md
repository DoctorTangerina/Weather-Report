# Correlation map for selected Variables and map areas

This interview draft is superseded by [the final specification](correlation-map-spec.md),
published as [GitHub issue #56](https://github.com/DoctorTangerina/Weather-Report/issues/56).

## Problem

Users need to compare several measurements together: different Variables within
one Selected area, one Variable across multiple Selected areas, or arbitrary
combinations of both. They need a numeric pairwise correlation result and a
readable visualization, with explicit explanations for unusable selections.

## What to build

Implement the full frontend, API and data-layer path. Users select a rectangular
Selected area and multiple Variables, add those entries, and optionally repeat
for another rectangle. They may also add prepared Derived series, remove entries
and choose a common period and temporal resolution before building a
Correlation map. Use already acquired data; this feature does not download new
NASA datasets.

Variable selections are independent for each rectangle. For example, users can
add temperature and precipitation from rectangle A, soil moisture from rectangle
B, and temperature and vegetation index from rectangle C. These five entries
form one Correlation map; rectangles do not have to share the same Variables.

## Selection and preparation

- Offer available acquired fields with units, timestamps and source metadata,
  plus Derived series. Preserve processing history.
- Require a common period. Keep matching native frequencies; where frequencies
  differ, offer explicit resampling to a common coarser frequency or selection
  changes. Let users select the aggregation for each input.
- Use the processing feature's mean, sum, minimum, maximum and median options,
  preserving physical measurement semantics. Never silently fill, upsample,
  nearest-match or preprocess inputs.
- Use a shared analysis time zone, default UTC, for aggregation and alignment.
  Prepared local-time filters retain their confirmed input time-zone semantics.
- Preserve list order and stable input identities. Prevent exact duplicate
  inputs. Labels identify Variable and Selected area, with dataset or
  Derived-series names where needed to disambiguate.
- Support ordinary rectangular boxes initially. Explain unsupported boxes
  crossing the antimeridian and unavailable coverage; let users redraw.

## Numeric processing

- Keep reusable numeric processing in the data folder, called by the API.
- Apply the existing acquisition Quality gate before resampling. Preserve source
  quality assessments and provenance from explicitly filled Derived series.
- Align inputs to matching timestamps on the common output timeline. Reject
  inputs with any missing output value; do not silently use pairwise reduced
  samples. An aggregate may use incomplete native observations: a monthly value
  can exist despite missing source days. An empty output bucket excludes its input.
- Exclude constant inputs. Return the reasons for every unavailable, excluded,
  incomplete or constant input without inventing a numeric correlation.
- Calculate exploratory Pearson correlation for every retained pair, including
  different Variables and different Selected areas. Two or more matching
  observations suffice when inputs vary; exactly two observations produce a
  warning. Do not suppress weak or zero scores.
- Return ordered IDs and labels, a symmetric numeric matrix, diagonal values
  of 1, analysis settings, observation count, warnings and excluded inputs with
  their reasons. Keep excluded inputs outside the numeric matrix.
- If fewer than two usable inputs remain, return explanations and a result
  state requiring selection changes rather than an empty or single-cell map.

## Frontend and API

- Provide selection, request, loading, result and failure states through the
  complete frontend/API flow.
- Render retained inputs as a heatmap with a fixed -1 to +1 scale. Selecting a
  cell shows the correlation score and the two input labels.
- Remove excluded inputs from the heatmap and list their explanations below.
  Missing-data exclusions also show a popup suggesting another period or Variable.
- Hide undefined correlations rather than treating them as zero; describe them
  separately. Constant inputs are removed as a whole.
- Preserve valid comparisons after individual input exclusions and show the
  two-observation warning when applicable.
- Do not impose a fixed number-of-inputs limit. On computational/resource
  failure, explain that users should reduce the number of inputs. Do not
  silently return a subset as though it were the complete requested result.

## Acceptance criteria

- [ ] Users can add multiple Variables from each selected rectangle and build
  comparisons within one Selected area, across Selected areas, or both.
- [ ] Each rectangle has an independent Variable selection; one matrix can
  combine different Variables from different rectangles without requiring the
  same Variable list in every rectangle.
- [ ] Source series and prepared Derived series participate with unambiguous
  labels, stable identities and preserved provenance.
- [ ] Common-period, frequency and explicit aggregation controls produce aligned
  output without implicit filling or sampling changes.
- [ ] An input missing even one output observation is excluded, while a valid
  aggregate with incomplete native observations remains eligible.
- [ ] Acquisition-excluded, unavailable and constant inputs receive clear
  explanations and do not appear in the numeric matrix or heatmap.
- [ ] Two complete varying observations are calculable with a warning; weak and
  zero correlations remain visible. Fewer than two usable inputs require changes.
- [ ] The API returns the numeric matrix and agreed metadata for the retained
  ordered list; frontend cell selection shows the corresponding score and labels.
- [ ] Missing-data popups, exclusion descriptions and resource-failure advice
  appear through the full frontend/API flow.
- [ ] Deterministic tests verify the public numeric boundary, API integration
  and frontend selection/result/error flows without NASA downloads.

## Dependencies and scope

Related: #46, particularly #48 for resampling/alignment and #51 for Pearson
infrastructure. #51's three-pair minimum does not apply to this feature; keep its
existing contract unchanged while supporting the explicit two-observation rule
here. Do not impose a blanket dependency on every processing-feature ticket.

Out of scope: new data acquisition, polygons and antimeridian-crossing selection,
automatic Discovery/Mirror changes, Evidence labels, automatic detrending or
seasonal removal, lag analysis, and implementation of additional temporal filters.

The agreed decision record is maintained in `docs/correlation-map.md`.
