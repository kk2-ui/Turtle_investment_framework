# CN:600887 Round 8 independent pre-outcome review — V2

## Verdict: AUTHORIZE

This re-review was limited to the prior independent review and the submitted
V2 judgment file; no new source, outcome, market, price, return, valuation, or
analyst material was accessed.

V2 cures the sole prior blocking defect. In A1 and A2, any product-level
mismatch now requires a `LOCAL_MISMATCH`, retains each comparable product's
local comparison, and produces only `PARTIAL_UNKNOWN` for the aggregate axis.
When all three products are comparable, `SUCCESS`, `FAILURE`, and `MIXED` are
explicitly the only applicable aggregate outcomes and partition the possible
comparisons. The four aggregate states are therefore mutually exclusive, and
the mismatch remains local rather than contaminating the other product results
or the other axes.

The V2 change is limited to that precedence/local-result clarification. It
does not add a defensive gate, expand the authorized observation set, substitute
a proxy, or change the judgment, facts, thresholds, responsibility boundaries,
or A3/A4 treatment. The prior return is accepted.
