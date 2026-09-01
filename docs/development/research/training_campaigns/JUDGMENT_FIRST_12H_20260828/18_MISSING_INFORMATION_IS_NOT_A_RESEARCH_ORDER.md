# Missing Information Is Not a Research Order

## Decision

`missing_information` is diagnostic. It may be empty, and its presence alone
does not create a new research task.

A new task is created only from a material `fragile_leap` that names the
current claim, why it is fragile, the evidence that would discriminate it, and
the company-judgment or investment consequence of reversal.

## Observed failure

The active review validator required at least one missing-information string.
The router then converted every such string into a research task. If public
information remained unavailable, the final reviewer kept the gap and the
next run recreated the same search.

The cheapest path to a formally complete review was therefore to invent a
gap, search it, record unavailability, and search it again later. This rewarded
audit motion rather than judgment improvement.

Root cause: `REASONING + MODEL`.

Economic impact: finite research time could be diverted from a material
customer, cash, permanent-loss, or valuation question to an immaterial or
already exhausted disclosure gap. Under the three-task cap, a blank or
misclassified consequence could also displace the issue most likely to change
the investor's conclusion.

## Runtime correction

- A complete independent review may use `missing_information=[]`.
- Missing-information notes remain visible but produce `NO_ACTION` by
  themselves.
- A routed `fragile_leap` must contain a claim, a fragility reason, needed
  evidence, and the purpose-specific consequence.
- Investment work uses `decision_consequence`; company-judgment-only work uses
  `judgment_consequence`.
- The consequence is carried into task materiality and priority rather than
  replaced with a generic report-level sentence.
- Company-judgment-only tasks cannot mutate decision or valuation ledgers.
- After an unavailable search has been converted into a bounded current
  treatment, retaining the disclosure gap does not recreate the task. A later
  task requires a new material fragile leap.

## What this does not do

- It does not hide unavailable evidence.
- It does not prevent research on a gap that can change normal earnings,
  owner cash, permanent loss, valuation direction, action, or a material
  monitoring decision.
- It does not turn lack of disclosure into positive or negative evidence.
- It does not add a report gate, score, minimum number of gaps, or source-call
  quota.

## Mechanical acceptance

- complete review with no missing notes: reviewed;
- diagnostic missing notes only: no research task;
- incomplete fragile leap with no material consequence: no research task;
- complete investment fragile leap: routed with its decision consequence;
- complete company-judgment fragile leap: routed with its judgment consequence
  and without decision/valuation mutation authority;
- public-information-unavailable result, fragile leap removed, note retained:
  no repeat task;
- existing complete governance, peer, operating, contract, and market routes:
  still executable.

This correction changes the reward: finding a gap earns nothing by itself.
Only a gap tied to a falsifiable, material judgment receives research budget.
