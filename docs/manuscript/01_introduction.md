# Introduction {#sec:introduction}

The package separates input acquisition from time-series alignment,
statistical summaries, and rendering. Its solar inputs include the daily
international sunspot number from WDC-SILSO [@silso]. F10.7 radio flux and
the Dst and ap geomagnetic indices are available through OMNI sources
[@omni]. The software groups commit observations by UTC calendar day and
preserves per-repository and aggregate series. The build described here uses
saved input snippets and existing repository-author artifacts.

A report answers a bounded exploratory question: how do paired daily series
vary together over a particular observation window? The shape of an
association depends on which dates, metrics, and transformations are used.
The package preserves intermediate tables so those choices can be inspected.
