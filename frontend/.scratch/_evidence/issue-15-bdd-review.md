# BDD Review: issue #15

Audience judged: customer-facing; students investigate a Discovery.
Source: issue #15 body retrieved via GitHub API earlier in this conversation;
BS-006 (US-002) and BS-008 (US-003). Reviewed 2026-11-14.

| Attribute | Questions | Result | Finding |
| --- | --- | --- | --- |
| Essential | Q4, Q10 | PASS | No removable setup or implementation mechanics. |
| Focused | Q11 | PASS | Student-visible outcomes rather than private implementation. |
| Singular | Q6, Q7 | REVISE | Original titles “Present possible causes as context” and “Show the evidence behind a Discovery” omit the action; revised titles below name the action and outcome. |
| Clear | Q12 | PASS | Meaning recoverable from the issue's ordered investigation and specified evidence fields. Final feedback wording remains unresolved. |
| Complete | Q2, Q3 | PASS | Covers all four specified scenarios. Undecided wording is not invented. |
| Unique | Q1, Q5 | PASS | Prediction, comparison, scientific context and provenance have distinct purposes. |
| Ubiquitous | Q9 | PASS | Uses student, Discovery, Region, Trends and Evidence label. |
| Integrous | Q8 | PASS | Given/When/Then order preserved. |

Re-run after title-only revisions: all eight attributes PASS. No behavioral change
or implementation verification is implied by this review.

## Revised scenarios

```gherkin
# BS-006 / US-002
Feature: Become a Detective investigation
  The student forms a hypothesis before seeing the evidence.

  Scenario: Ask for a prediction before showing the charts
    Given the student opens a Discovery for investigation
    When the investigation starts
    Then the student is asked which Region they think is changing faster, before any chart is shown

  Scenario: Compare the guess with the data
    Given the student has answered the prediction question
    When the student continues
    Then the student sees the charts of both Regions and whether the guess matched the computed Trends

  Scenario: Reach the final step and see possible causes labeled as context
    Given the student has seen the comparison
    When the student reaches the final step
    Then each possible cause is labeled as context from scientists and not as a result of the data

# BS-008 / US-003
Feature: How do we know?
  The student can see why a Discovery deserves trust.

  Scenario: Open How do we know? and see the evidence behind a Discovery
    Given a student viewing a Discovery
    When the student opens "How do we know?"
    Then the student sees the NASA source, the period analyzed, the rate per decade with its 95% interval, the Evidence label and the citation of the method paper
```

### Unresolved behavior

The issue leaves the number of prediction options and feedback wording undecided.
Implementation preserves the pre-existing two stub options and match/mismatch text.
No new decision about their final editorial design is inferred.

Later user instructions specify that the investigation stays in the initial-page
sidebar, the selected prediction and Check the data are filled, and How do we know?
is absent from Predict. They supplement the scope; the issue's original Gherkin is
not silently rewritten to include these later decisions.
