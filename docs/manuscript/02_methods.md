# Methods {#sec:methods}

The alignment layer joins daily series by date. An activity series can
include a known zero-count day. A missing geophysical observation lacks a
measured magnitude. The paired analysis retains dates with observations for
the comparison, preserving these distinct meanings.

Reports include Pearson correlation for a linear association, Spearman
correlation for rank association, and Kendall correlation for concordance.
The lag profile evaluates association after shifting one series against the
other. A rolling view repeats the selected statistic over moving windows.
Depending on the run options and available overlap, further exports can
include prewhitened cross-correlation, autocorrelation diagnostics,
periodograms, and resampling intervals.

The local tests check parser behavior using saved file snippets and report
behavior with synthetic daily input. The archived report and plot in this
paper are replayed as recorded artifacts without rerunning acquisition or
estimating another association.
