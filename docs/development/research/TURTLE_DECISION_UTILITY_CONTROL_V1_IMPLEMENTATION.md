# Decision Utility Control v1

Status: `IMPLEMENTED / SYNTHETIC_CONTROL_VALIDATED / REAL_DECISION_UTILITY_EVALUATION_PENDING`

## Purpose

Decision utility is not a forecast score and not an investment authorization.
It records whether a pre-registered enhanced research method materially changed
the decision support available under the *same* frozen Decision Contract and
evidence budget.  Its only possible output is `CANDIDATE_ONLY`.

## Canonical sequence

```text
Forecast V6 + frozen Decision Contract
  -> Forecast Pairing V3 (frozen company-and-time outcome-window holdout, before outcome access)
  -> Decision Utility Pairing (before outcome access)
  -> independent custodian settlement
  -> registered Forecast paired evaluation
  -> independent Decision Utility Evaluation
```

The control plane resolves the Forecast Pairing, Forecast, Decision Contract,
paired evaluation and settlement from its append-only tables.  The caller
cannot supply an alternative settlement reference or an ad-hoc holdout.

## Controls

- Only Forecast V6 is accepted: the enhanced method therefore has a frozen
  program/version/freeze identity, rather than a reused string label.
- The utility pairing must use the exact Forecast Pairing V3, its same frozen
  company-and-time holdout, the same Decision Contract and its one H1 evidence
  budget, plus exactly the pairing's baseline and enhanced method IDs. V3
  derives the unseen economic cluster and non-overlapping outcome windows from
  the registered training program.
- A new utility pairing is rejected at or after the canonical holdout outcome
  window, and after custodian outcome access. Its payload timestamp must equal
  the append-only control-plane timestamp; exact immutable replay remains
  available for operational retries.
- The evaluation must cite the stored paired forecast evaluation. It derives
  the exact settlement from that object and rejects a caller-written outcome
  reference or holdout.
- Reviewer identity must differ from both the forecast owner and outcome
  custodian; material dimensions are permanent-loss guardrail, owner-cash
  access, key unknown discovery and research cost.
- Neither object can name CJO, valuation, report, investment, BuyBand or a
  release permission. No aggregate score is calculated.

## Boundaries

This control does not turn historical replay into prospective evidence, does
not release a method, and does not alter an active Forecast policy. A real
decision-utility claim still requires a separately frozen V6 forecast,
pre-outcome baseline and canonical dual-axis holdout; none is registered by
this implementation.
