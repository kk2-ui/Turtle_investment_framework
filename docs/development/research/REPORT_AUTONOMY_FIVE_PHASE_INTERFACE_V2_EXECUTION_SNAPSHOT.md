# Stage-5 interface-v2 execution snapshot

## State

`PREOUTCOME_EXECUTION_COMPLETE_NOT_COMPARABLE`.

The repaired replacement cohort executed all 32 registered cells exactly once.
No post-cutoff outcome source, price, return, valuation result, or investment
action was opened. No cell was retried or manually rewritten.

| Cell state | Count |
| --- | ---: |
| `FROZEN` complete Episode + first reader report | 9 |
| `EPISODE_INVALID` terminal failure | 23 |
| `NOT_STARTED` | 0 |

The nine valid cells are distributed across only four cases:

- CASE:01 — A00, A01, A10
- CASE:02 — A01, A10, A11
- CASE:03 — A10, A11
- CASE:07 — A11

No case has all four valid arms. Therefore no self-contained anonymous
four-arm packet can be built for any case, and the preregistered anonymous
review freeze receipts cannot be satisfied. The outcome-access gate remains
`BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN`.

## What this establishes

The v2 task/validator interface defect was genuinely repaired: the first three
replacement cells that completed all required fields passed through Episode,
downstream bundle, and reader-report materialization. The remaining failures
are substantive one-shot contract failures—mostly normal-earnings bridge
authority, component coverage, route eligibility, sensitivity input shape, or
JSON completeness—not a provider/API or post-outcome contamination issue.

This is not evidence that industry memory, expert correction, or their joint
use improves report quality. The registered treatment effect is unidentifiable
because the experiment has no complete within-company four-arm comparison.

## Required next design step

Do not alter this cohort or reinterpret terminal failures. Build a separately
identified follow-up in which the research judgment is collected as a staged,
price-free ledger first, then a deterministic compiler binds that ledger into
the strict reader-report contract. The follow-up must preregister:

1. a minimal judgment packet whose required fields are directly answerable from
   the common source package;
2. a separate contract-completion/compiler stage with explicit diagnostics;
3. the same four-arm memory randomization, equal budgets, fresh-agent
   isolation, no-retry rule, anonymous review, and sealed outcome plane; and
4. acceptance criteria that require at least one complete four-arm case before
   outcome settlement is even eligible.

Until that follow-up is independently reviewed and frozen, the industry and
expert memory layers remain useful as hypotheses and acquisition prompts, but
their autonomous report utility is **not proven**.
