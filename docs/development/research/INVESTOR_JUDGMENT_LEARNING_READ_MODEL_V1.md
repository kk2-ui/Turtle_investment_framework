# Investor Judgment Learning Read Model V1

## Investor purpose

This read model answers a practical question that completion receipts alone do not answer:

> Did Turtle merely complete a training pipeline, or did it obtain evidence that should change how an investor judges a company?

It separates six evidence classes:

1. pipeline proof;
2. bounded real-company findings;
3. measurement learning;
4. method utility;
5. cross-company transfer evidence;
6. invalidated evidence.

It does not create a total judgment score, rewrite a source receipt, or authorize CJO, valuation, reports, buy bands or investment actions.

## Current conclusion

The strict current ceiling is `L1`.

This means Turtle has repeatedly frozen, acquired and mechanically settled real company outcomes from official sources. It has also produced useful bounded findings:

- Round 5 changed what may be credited to Fujian Cement's Furun arrangement;
- Round 6 showed development utility from separating legal progress, issuer control, consolidation and customer realization;
- Round 7 showed development utility from keeping industry conditions, execution, customer response, unit economics, cash and permanent loss separate;
- Round 8 validly found no material method advantage;
- Round 9 preserved useful company facts while invalidating the method comparison itself.
- Round 10 expanded the real denominator to three more appliance company-cutoffs: Huadi and Zhejiang Meida added six replayable issuer-level fields, while Robam retained three annual-report-version mismatches. The external review found `NO_MATERIAL_UTILITY` for the eight-dimensional method.

Across the six recorded batches, eight company-cutoffs are represented. Seven contain at least one mechanically observed field; one is mismatch-only. The field denominator is 77: 45 `OBSERVED`, 22 `UNKNOWN`, and 10 `MEASUREMENT_MISMATCH`.

It has not yet produced a formally accepted `L2` mechanism-pair verdict, an `L3` admitted primary-path result, a validated `L4` learning transfer, or an `L5` multi-episode relative comparison.

## Why the ceiling is conservative

Positive development utility is not the same as formal transfer. Round 6 used a different company, but repository-memory exposure and the absence of a complete `LNOTE -> pre-freeze field change -> same-definition settlement` chain prevent an `L4` claim.

Likewise, Round 8's `NO_ADVANTAGE_PROVED` is useful negative evidence, not a method success. Round 9's accepted outcome settlement does not rescue a comparison produced by a broken frozen resolver. Round 10 proves that issuer-level financial fields can be replayed without proving customer response, action effect, unit economics, owner cash, or a material advantage for the enhanced method.

## Structured inputs and output

The read model consumes only the explicit JSON manifest at `docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1_MANIFEST.json`. Single-company entries bind a completion receipt, cell-level settlement, independent review and optional invalidation receipt. The Round 10 multi-company adapter binds its pre-outcome freeze, terminal field-count completion receipt and external method review. It consumes no outcome values or directions. The implementation does not infer evidence status from the investor readout.

Generate or verify the current projection with:

```bash
.venv/bin/python scripts/investor_judgment_learning_read_model.py \
  --repo-root . \
  --manifest docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1_MANIFEST.json \
  --output docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1.json

.venv/bin/python scripts/investor_judgment_learning_read_model.py \
  --repo-root . \
  --manifest docs/development/research/INVESTOR_JUDGMENT_LEARNING_STATUS_V1_MANIFEST.json \
  --check-only
```

## Next evidence that matters

The next useful milestone is not another broad completion count. It is one clean `L2` mechanism-pair settlement:

- the primary and rival mechanisms must predict different frozen observations;
- the original resolver and measurement contract must survive outcome access unchanged;
- the independent review must accept the diagnostic verdict;
- `UNKNOWN`, `MIXED`, `NOT_DIAGNOSTIC` and `MEASUREMENT_MISMATCH` must remain in the denominator.

Only after that accepted lesson changes a different company's pre-outcome research fields and is settled under the same definition should Turtle claim `L4` transfer evidence.

## Research-agenda projection

`scripts/investor_judgment_research_agenda.py` converts this status into a research-planning-only handoff. The explicit `INVESTOR_JUDGMENT_RESEARCH_AGENDA_V1_POLICY.json` classifies every source `next_evidence` item instead of assuming that every company follow-up transfers. The projection keeps the evidence classes separate:

- Round 5 local lessons and Round 6/7 development utility become replication-required question or acquisition candidates;
- issuer-specific follow-up remains in a company continuation agenda;
- Round 8 remains a no-advantage caution while its valid measurement and experiment lessons may enter redesign-required candidates;
- Round 9 remains quarantined and can inform only failure-mode design for a new method epoch;
- Round 10 remains a no-material-utility caution; only its mechanism-field and annual-report-route remediations enter redesign candidates;
- unreviewed evidence is excluded from both company context and candidate rules.

The generated `INVESTOR_JUDGMENT_RESEARCH_AGENDA_V1.json` authorizes only `RESEARCH_AGENDA_ONLY`. It cannot amend CJO, valuation, reports, buy bands or investment actions.
