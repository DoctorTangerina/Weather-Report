# Explicit linear detrending — issue #53

Source: [issue #53](https://github.com/DoctorTangerina/Weather-Report/issues/53),
BS-013 (US-002, DS-005), with Q1–Q6 approved by the user in the design interview.
The decisions below are agreed and implementation was authorized after the
interview. This document records behavior, not implementation evidence.

## Agreed behavior

Linear detrending is an explicit, ordered Processing recipe step for Explore My
World. It consumes one Source series or Derived series at its position in the
Processing recipe and returns a Derived series without changing its input.
It applies to 3-hourly, daily and monthly Series. No detrending is applied when
the Processing recipe does not request it.

- **Q1 — Mean convention:** support both subtracting the complete fitted line
  and removing the fitted inclination while preserving the mean of valid input
  values. The caller must explicitly choose; there is no default convention.
  For equally spaced values `[20, 22, 24]`, the respective results are
  `[0, 0, 0]` and `[22, 22, 22]`, within floating-point precision.
- **Q2 — Estimator:** ordinary least squares with an intercept, against actual
  elapsed time between observations, interpreted in UTC. Do not use observation
  index as elapsed time. Do not remove outliers automatically. For days 1, 2 and
  4, values `[10, 12, 16]` are exactly linear in elapsed time.
- **Q3 — Fitting sample:** use the valid values in the immediate input,
  including values explicitly filled by earlier steps. Keep missing positions
  missing and retain the per-observation filled flags and source provenance.
  A missing-value operation before detrending can change its fitting sample;
  one after detrending does not retroactively change the fit.
- **Q4 — Minimum sample:** require at least two valid observations at distinct
  timestamps. With fewer, return an explanatory error. Two observations are
  sufficient for the calculation; this operation does not attach a statistical
  significance assessment to the fit.
- **Q5 — Constant input:** accept constant Series. Values `[5, 5, 5]` return
  `[0, 0, 0]` when the complete line is subtracted, or `[5, 5, 5]` when preserving
  the mean.
- **Q6 — Supported limits:** support the Gregorian calendars already interpreted
  by the processing boundary. Return an explicit error for other calendars or
  an unrepresentable nonfinite result, without changing any supplied input.

Timestamp labels, units, Time step, Aggregation, source quality and lineage
remain available through the result and provenance conventions of the existing
public processing boundary. The reusable Processing recipe records the chosen
mean convention and operation order. Replay fits the immediate replacement input;
it does not reuse coefficients fitted to the previous observations.

## Scope and verification

Implementation and deterministic tests use the existing public data-processing
callable boundary S1 (`process_series`). Tests cover both BS-013 scenarios and
the approved numerical conventions and boundary cases. No HTTP endpoints,
frontend components or live downloads are part of this issue.

Seasonal removal, lagging, time shifting and automatic outlier removal are outside
scope. This operation does not change the automatic Discovery engine, Trend
analysis, Mirror preprocessing or Evidence labels governed by the existing ADRs.

The estimator and mean convention are processing choices. They are recorded here
rather than changing the automatic engine methodology in ADR-0002.
