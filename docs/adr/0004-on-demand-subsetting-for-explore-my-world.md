# On-demand subsetting with background jobs for Explore My World

Every Explore My World request that the seed set cannot answer (any Selected area, and any Time step finer than monthly) is fetched by subsetting NASA data on demand for exactly that area, Variable and period. The fetch runs as a background job that the UI follows until it finishes, and the result is cached. Requests are capped: at most 1 year for 3-hourly and 10 years for daily. Monthly catalog Region Series stay instant from the seed set, and the Discovery engine keeps using only those.

We chose this over pre-downloading because hourly global data for 25 years is roughly 180 GB per Variable before compression, far beyond the 47 GB of monthly files kept today. We also chose it over reading those local monthly files when they happen to be present: they exist only on the machine that built the seed set, so the app would behave differently depending on where it runs. The local files remain an input to the offline seed build only. The costs are that Explore My World needs an Earthdata token and network access, a first request can take minutes, and the caps limit how long a sub-monthly period a user can explore.

Status: accepted
