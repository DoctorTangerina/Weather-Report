# NASA Challenge: Earth Science Trend Detective (original brief)

## Challenge

Change is always occurring in the Earth's interconnected environmental system. When it runs in a consistent direction (rising or falling, increasing or decreasing, thickening or thinning), measured variables reflect it. But a measured Earth science variable can trend one way in one region and the opposite way in another, even when the same process drives both. The multitude of variables makes it hard to select ones that indicate change, and then to analyze them.

**Goal:** create a tool that can select variables measured by Earth science missions or produced by Earth science models, visualize how they change over time, and determine:

- **what** is changing,
- **where** it is changing,
- **how much** it is changing,
- whether the change is "significant" in the scientific sense.

## Background

- Satellite instruments observe land, atmosphere and oceans. Global models combine satellite and other data to characterize the Earth system.
- A **trend** is change moving in a consistent direction over time. It points to the processes causing the change and the processes that respond to it.
- Two sub-problems:
  1. Finding variables that are trending, from simple ones (temperature, rainfall) to complex ones (evaporation, streamflow).
  2. Analyzing trends in particular regions of land, ocean, or atmospheric levels. Some trends are global, but most are not.
- Instruments providing variables: MODIS, OMI, AIRS, GPM.
- Models providing many more: MERRA-2, GLDAS.

## Objectives

A successful response brings together:

1. **Identify variables** of interest that can be investigated for trends.
2. **Acquire the data** for a particular region.
3. **Generate and visualize a time series** for the variable and region over a long enough period for statistical analysis.
4. **Perform a basic statistical analysis** of the series: rate of change over time, and a significance test (t-test, Mann-Kendall test, or confidence intervals).

A response that does both the visualization and the analysis meets the full scope.

## Potential considerations (optional)

**Audience**
- Likely high school and college students, plus members of the public with some scientific background.
- Simple definitions of variables would help considerably.
- Frame users as "data detectives": find variables, then decide whether they trend and whether the trend is significant.

**Approach**
- Ask the user a short series of questions (what / where), then search related variables.
- Provide a couple of demonstration examples the user can watch.
- Optionally use AI to suggest data with trend potential in particular areas, drawing on news articles, research papers, or region characteristics (desert, rain forest, tidal estuary, atmosphere above a large city).

**Working with the data**
- Temporal resolutions: hourly, 3-hourly, daily, monthly. Daily and monthly are the easiest to process.
- A trend is interesting even if not significant. A longer record may make it significant.
- Consider public hydrological plotting tools such as CUAHSI.
- Trends can be non-linear, and some only show once regular cycles (e.g. seasonal) are removed. That is beyond scope. **Detecting and analyzing linear trends is a great start.**

## NASA data and resources

- **Giovanni**: menus of many variables; generates and downloads time series.
- **Hydrology Time Series**: time series for hydrological data.
- **AppEEARS**: access and transform geospatial data from federal archives; includes time-series generation.
- **Climate Data Online (CDO)**: NCDC archive of historical weather and climate data, station history, mapping tool.
- **Research article**: time-series analysis of remotely sensed SeaWiFS chlorophyll in river-influenced coastal regions (time-series creation and significance testing).

## Space agency partner resources

- **KNMI Climate Explorer**: web tool to explore, analyze and visualize climate data.
- **Statistical test methods to detect trends in time series data**: article on trend testing.
- **A Comprehensive Guide to Statistical Significance**: guide to significance testing.
- **CSA (Canadian Space Agency)**:
  - Radarsat Constellation Mission (RCM) data: maritime surveillance, disaster management, ecosystem monitoring.
  - Geo.ca: Canada's open geospatial information.
  - SWOT mission information: surface water elevation of lakes, rivers, reservoirs and oceans (NASA/CNES, with CSA and UK Space Agency).
  - Monitoring and protecting our ecosystem from space.
  - Synthetic Aperture Radar Python tutorial (Python and QGIS).

## Glossary

- **Trend**: consistent change in one direction over time.
- **Significant trend**: a trend unlikely to be due to chance, judged with a t-test, Mann-Kendall test or confidence intervals.
- **Time series**: a variable's values for a region over time (daily or monthly).
- **Seasonal cycle**: regular yearly variation that can hide a trend; removing it is beyond the baseline scope.

