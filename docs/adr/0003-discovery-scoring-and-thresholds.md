# Fixed-tier Discovery scoring and evidence-gated thresholds

The engine decides what counts as a Contrast, a Mirror and a Surprising pair, and how a Candidate Discovery is scored, with fixed thresholds and fixed score tiers. We chose fixed rules over tuning them against the data, so the ranking can be explained to students and audited (ADR 0001), and so the thresholds cannot be fitted to produce the Discoveries we hoped for. The cost is that every value below is a judgment call; each belongs in one named constant in the code and none is claimed to be optimal.

- **Magnitude gap.** Two same-direction Trends contrast when the faster rate is at least twice the slower and their 95% intervals do not overlap. A pair of Trends that fails the interval test is not a Contrast. The one exception is a pair in which neither Trend is significant: it is kept as a Candidate labeled "Not enough evidence yet" on the ratio alone, and is never the headline.
- **Multi-Variable.** A Variable counts only if it is itself a Contrast. A Variable that both Regions share in direction and rate is context, not a Contrast.
- **Evidence label.** A Discovery carries the weakest label among the Trends it lists. A Contrast with a "Not enough evidence yet" Trend is dropped when the pair has a Contrast that rests on evidence, so noise on one Variable cannot weaken a sound result on another.
- **False-discovery rate.** One q of 0.05 for the whole engine, matching the 95% intervals students see. With about 96 comparisons this leaves fewer Discoveries (ADR 0002).
- **Surprising pair.** Two Regions whose bbox centers lie within 2,500 km (13 of the 276 pairs in the catalog) and that have a Contrast. The distance is a placeholder, to be revisited once real Discoveries exist.
- **Mirror.** |r| of at least 0.3 on the deseasonalized, detrended monthly series, and significant after Benjamini–Hochberg correction across every pair tested. With about 300 months, significance alone would accept correlations too weak to teach anything.
- **Score.** The sum of fixed components: opposite sign 100, multi-Variable 20, surprising pair 20, magnitude gap up to 10 (from the rate ratio, capped), Mirror 5 for each Mirror that is significant after correction. The order the spec fixes (opposite signs, then multi-Variable and surprising pair, then magnitude gap) holds whatever the data, because each lower tier's maximum is below the tier above it. Evidence gates headlining; it does not change the score.
- **Lead Contrast.** The Contrast with the highest score, listed first; it alone drives the question and the Predict, Check and Reason steps.
- **Outlier check.** It reruns the Trend without its single most extreme month.
- **Surprise Me!.** A weighted draw by score among the top 5 unseen, headline-eligible Candidates. A Discovery is never repeated in a session; a Region is avoided, but the rule gives way when no Candidate with a fresh Region is left.
- **Predict.** Two options, the two Regions, and the faster one is the answer.

Status: accepted
