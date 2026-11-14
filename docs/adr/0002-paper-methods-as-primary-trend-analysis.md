# Paper methods as the primary trend analysis

Trends follow the method of the SeaWiFS chlorophyll time-series paper (cited on "How do we know?"). Primary: remove the seasonal cycle, then a least-squares linear fit with an F-test and R², plus a linear fit on annual anomalies and a robust regression with an outlier check (rerun without the most extreme month). Theil–Sen with Mann-Kendall is a cross-check: agreement between methods supports the "Strong evidence" label, disagreement caps it at "Some evidence". Because the engine tests many Region pairs and Variables, results also get Benjamini–Hochberg false-discovery correction and an autocorrelation correction for monthly data. We chose the paper's methods over a purely non-parametric approach so students see a method published for NASA data; the cost is more computations per Trend and fewer Discoveries surviving.

Status: accepted
