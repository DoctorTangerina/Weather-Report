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
The values of one Variable over one Region or Selected area across a period, one value per Time step, each combining the area's grid cells by an Aggregation, together with a record of its quality. The Discovery engine only uses monthly Series of catalog Regions combined by the area-weighted mean; other Time steps, Aggregations and Selected areas exist only for the user's own exploration.
_Avoid_: Time series, data, curve

**Aggregation**:
The rule that combines the values of an area's grid cells into one value for a Time step: mean, median, minimum, maximum, root mean square, standard deviation (of the whole population of cells, not a sample), or mean absolute value. Every rule except minimum and maximum counts each cell in proportion to its area. When the Time step is longer than the data's own, the area's values are combined over space first, then over the Time step by the same rule (a daily maximum is the highest of the area's values that day).
_Avoid_: Composition, strategy, reducer

**Time step**:
The interval between consecutive values of a Series: 3-hourly, daily or monthly. Days and 3-hour intervals follow UTC. Precipitation is given as the total that fell during each Time step.
_Avoid_: Granularity, resolution, frequency

**Quality gate**:
The check that decides whether a Series has enough valid data to be used: too large a share of missing Time steps, or, for a land-only Variable, too little of the Region being valid land.
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

**Selected area**:
A geographic area a user draws on the map in Explore My World: one rectangle, or several touching or overlapping rectangles joined into one shape. It may cross the antimeridian. A user has at most one Selected area at a time, and it lasts only until the page is reloaded. It is distinct from a named Region in the fixed Region catalog and never becomes one.
_Avoid_: Custom area, box, polygon

**Source series**:
A Series as acquired, before any Processing recipe is applied.

**Processing recipe**:
An ordered list of processing steps applied to one or more Series, which can be replayed to reproduce the same result.
_Avoid_: Recipe (on its own), pipeline, workflow, transformation

**Derived series**:
The result of applying a Processing recipe to one or more Source series. It keeps its Processing recipe and the provenance of its inputs.

**Linear detrending**:
An explicitly selected Processing recipe step in Explore My World that removes a fitted linear change from a Series, either preserving its mean or returning deviations around zero. The Source series is preserved; the result is a Derived series.
_Avoid_: Automatic trend removal, seasonal removal

**Field map**:
The values of one Variable in every grid cell of a Region or Selected area at one Time step, drawn on the globe at the data's own resolution. Its colour scale spans that Variable's range over the area and period, so every Time step is drawn on the same scale.
_Avoid_: Heatmap (reserved for the Correlation map display), raster, layer

**Correlation map**:
A pairwise correlation matrix for a user-selected list of Source series or Derived series, which may represent different Variables and Selected areas.

## Experiences

**Surprise Me!**:
The experience where the engine selects a Discovery automatically and presents it to the user with the two Regions highlighted on a map and a thought-provoking question.

**Become a Detective**:
The experience where the user investigates a Discovery by comparing charts, answering hypothesis questions, and reading explanations of what the data indicate.

**How do we know?**:
The part of an investigation that shows the NASA source, the period analyzed, and the statistical assessment in plain language.

**Explore My World**:
The experience where the user freely picks catalog Regions or Selected areas, up to five Variables, an Aggregation and a Time step, sees their Series and Field maps, and processes Series with Processing recipes. Nothing made here feeds the Discovery engine.
_Avoid_: Manual investigation
