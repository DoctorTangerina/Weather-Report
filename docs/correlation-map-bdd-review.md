# Correlation map — BDD quality review

Source: the agreed Q1–Q32 interview, final independent-rectangle clarification,
and shared-scope confirmation, recorded in correlation-map.md.

Reviewed correlation-map-spec.md against all 12 BDD quality questions: feature
questions once per Feature, scenario questions for every scenario/outline, and
step questions for every step. Numerical examples instantiate the agreed rules;
they do not introduce new thresholds.

| Attribute | Questions | Result | Evidence |
|---|---|---|---|
| Essential | 4, 10 | PASS | Fixtures distinguish sampling, eligibility, numeric or visible outcomes without helper details. |
| Focused | 11 | PASS | Requests and observable results are declarative; no private calls or UI selectors are prescribed. |
| Singular | 6, 7 | PASS | Every scenario has one When and a title naming its action/outcome. |
| Clear | 12 | PASS | Concrete labels, values and timestamps distinguish undefined, missing and zero correlation. |
| Complete | 2, 3 | PASS | Agreed branches cover independent selections, resampling, exclusions, two points, visualization and failure; undecided operational details remain notes. |
| Unique | 1, 5 | PASS | Each Feature states its outcome; repeated input classes use outlines where the action/result structure matches. |
| Ubiquitous | 9 | PASS | Region is kept distinct from Selected area; Source series, Derived series and Correlation map follow the glossary. |
| Integrous | 8 | PASS | Given setup precedes one When and externally observable Then results; outlines supply placeholders. |

Structural checks verify unique IDs, resolved references, one action per scenario,
and seven BS entries mapped to the confirmed S1/S2/S3 verification seams. This is
a specification review, not a claim that implementation tests have passed.
