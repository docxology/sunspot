# Reproducibility {#sec:reproducibility}

The repository keeps source parsing, date alignment, statistics, and report
rendering testable in isolation. The offline report fixtures use known
daily input values and synthetic activity counts. The publication build
copies the saved author example plot into the render output and pairs it
with explicit accessibility metadata. The archived report JSON remains the
authority for the reported coefficients.

The pinned build writes PDF and HTML from these numbered sections, plus a
validation report and rendered provenance. Saved artifacts and synthetic
fixtures make this description reproducible without external data services.
