# Canonical CJO report binding v1

Status: implemented and synthetic-validated in the historical-training
worktree. This control binds a report read to canonical judgment artifacts; it
does not authorize publication, trading, a real CJO, or a real BuyBand.

## Contract-bound read

An `analysis_contract.json` may declare exactly one optional
`canonical_judgment_refs` object:

```json
{
  "frozen_cjo_ref": "canonical/frozen_cjo.json",
  "current_company_cjo_admission_ref": "canonical/current_company_cjo_admission.json",
  "investment_overlay_ref": "canonical/investment_overlay.json"
}
```

Once present, these are the sole production references. The ordinary
`read_judgment_generation_handoff` entry point resolves them from the contract;
caller-supplied CJO or overlay paths cannot substitute a different artifact.
`JUDGMENT_SYNTHESIS` reads the Frozen CJO. `INVESTMENT_ENRICHMENT` requires
all three references and verifies that the admission is `PRIMARY_ADMITTED`,
that it exactly binds the Core review and Frozen CJO, and that the overlay
reproduces the same CJO identity:
`cjo_id`, company, cutoff, method version, and resolution.

The overlay remains `CANDIDATE_ONLY`. A `NO_PRIMARY` or `MIXED` CJO retains its
own closure rules; this handoff never turns a projected valuation range into
investment or trading authority.

## Read receipts and release boundary

The synthesis receipt now records the canonical CJO file it actually read.
An investment-enrichment receipt separately records the CJO, admission and
overlay. Changing a contract reference or any canonical file invalidates the
corresponding receipt. Report assembly continues to require a current
`JUDGMENT_SYNTHESIS` receipt and, for a contract-bound investment report, a
current `INVESTMENT_ENRICHMENT` receipt.

These receipts prove controlled consumption only. Publication keeps its own
existing completion and review gates, and no receipt grants CJO mutation,
method release, price access, or trade execution.

## Boundaries

- Legacy reports without `canonical_judgment_refs` remain on their legacy
  ledger path and cannot claim CJO Core v1 integration.
- The binding does not add a second report truth source: report projections
  remain read-only slices of the referenced CJO and overlay.
- No Forecast, Measurement Contract, outcome, R-103 material, real CJO, or
  real price snapshot is read or changed by this work package.
