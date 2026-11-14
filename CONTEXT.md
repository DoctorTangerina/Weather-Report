# Autonomous Discovery Engine

A tool that analyzes NASA Earth science time series, finds notable contrasts between regions by itself, and turns them into investigations that teach students about trends and statistical evidence. The original challenge text is in `docs/challenge-brief.md`.

## Language

**Region**:
A named geographic area from a curated catalog, with a short plain-language description.
_Avoid_: Area, zone, location, cell

**Region catalog**:
The fixed list of Regions the engine and the user can choose from. Users cannot define a Region outside it.
_Avoid_: Region list, atlas

**Variable**:
A measured or modeled Earth science quantity (e.g. temperature, precipitation) with a plain-language definition.
_Avoid_: Metric, parameter, indicator

**Variable catalog**:
The fixed list of Variables the engine and the user can choose from, each with its NASA source, units and plain-language definition. Users cannot add a Variable outside it.
_Avoid_: Variable list, dataset list

**Series**:
The monthly values of one Variable over one Region across a period, averaged over the Region's area, together with a record of its quality.
_Avoid_: Time series, data, curve

**Quality gate**:
The check that decides whether a Series has enough valid data to be used: too many missing months, or, for a land-only Variable, too little of the Region being valid land.
_Avoid_: Filter, validation

**Excluded series**:
A Series that failed the Quality gate. It keeps its reasons but no values, and takes no part in any Trend, Mirror or Candidate Discovery.
_Avoid_: Dropped series, bad series

**Trend**:
The direction and rate of change of one Variable over one Region across a period, together with its uncertainty and statistical significance.
_Avoid_: Slope, change, tendency

**Evidence label**:
The plain-language rating of how strongly the data support a Trend or Discovery: Strong evidence, Some evidence, or Not enough evidence yet. Shown to students. A Discovery carries the weakest label among the Trends it lists.
_Avoid_: Confidence level, grade, p-value badge

**Method citation**:
The reference to the paper whose time-series methods the engine uses to evaluate Trends and rate their evidence. It credits the method, not the data: the paper's own Variables are not the Variables the app shows, so the same citation applies to every Discovery.
_Avoid_: Data source, paper for this Variable

**Mirror**:
Two Series, possibly of different Variables in different Regions, that move together or in opposite directions month to month beyond what chance explains.
_Avoid_: Correlation pair, teleconnection

**Contrast**:
One Variable on which the two Regions of a Discovery differ: their Trends run in opposite directions (an _opposite-sign_ Contrast), or run the same way at rates the data can tell apart (a _magnitude-gap_ Contrast). A Discovery has one or more Contrasts; with Contrasts on more than one Variable it is multi-Variable.
_Avoid_: Difference, divergence, comparison, multi-Variable contrast (say a Discovery with more than one Contrast)

**Lead Contrast**:
The Contrast of a Discovery that scores highest, and the first in its list of Contrasts. It alone drives the question and the Predict, Check and Reason steps of an investigation; the Discovery's other Contrasts are supporting evidence.
_Avoid_: Headline (reserved for whether a Discovery may open Surprise Me!), main contrast, headline Variable

**Surprising pair**:
Two Regions that lie close together yet have a Contrast, so that neighbours which should behave alike do not.
_Avoid_: Odd couple, anomaly

**Discovery**:
A pair of Regions whose Contrasts or Mirrors, on one or more Variables, are notable according to the engine's score.
_Avoid_: Finding, insight, result

**Candidate Discovery**:
A Discovery the engine has found and scored but not yet selected for presentation to a user.
_Avoid_: Proposal, lead

## Experiences

**Surprise Me!**:
The experience where the engine selects a Discovery automatically and presents it to the user with the two Regions highlighted on a map and a thought-provoking question.

**Become a Detective**:
The experience where the user investigates a Discovery by comparing charts, answering hypothesis questions, and reading explanations of what the data indicate.

**How do we know?**:
The part of an investigation that shows the NASA source, the period analyzed, and the statistical assessment in plain language.

**Explore My World**:
A later experience where the user freely chooses any region of the planet, beyond the Region catalog. Not part of the MVP.
