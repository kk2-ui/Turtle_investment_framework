# Course 2C multi-period acquisition review

Date: 2026-08-31 (Asia/Shanghai)
Verdict: **PASS**

Review scope: `scripts/enterprise_judgment_real_mechanism_training.py`, `scripts/outcome_measurement_acquisition.py`, `tests/test_enterprise_outcome_multi_source_acquisition.py`, and the directly affected legacy/consumer tests. The code author and reviewer are separate. No real outcome artifact was opened and no external model API was called.

## Investor-relevant conclusion

The multi-period acquisition module is now fit to enter Course 2C preregistration. A cutoff-period official fact remains bound to its source report and component; converted amounts reach both working-capital and V4 consumers in their destination unit; a legitimate repeated source fact remains one observation; and an internal component-identity contradiction is rejected at contract validation. These are the necessary controls for keeping mature-core normal earnings, owner cash, funding pressure, and the named growth cohort separate rather than creating a false result from data plumbing.

This is an acquisition/consumer-admission acceptance only. It does not establish that Qilianshan's growth capital earned its cost of capital, that the industry Pack has transfer utility, or that either A/B arm will be superior.

## Returned findings closed

### 1. Legacy V3 availability compatibility — closed

Root cause previously: `ACQUISITION_MODULE`.

The stricter availability identity now applies only to the new multi-source shape. The frozen single-source V3 contracts retain their pre-existing unknown-availability semantics; they are not retrospectively required to know a future publication date. Multi-source contracts still reject missing, mixed-precision, and cutoff-or-earlier availability.

Economic consequence: Round 9 freezes again reconstruct without weakening the new multi-report custody boundary.

### 2. Frozen conversion reaches consumer inputs — closed

Root cause previously: `ACQUISITION_MODULE` + `MODEL`.

Each raw record is converted from its frozen conversion before consumer projection. The deterministic-cell formula retains its signed arithmetic, while consumer facts apply the absolute scale and let the consuming accounting formula own the sign. V4 destinations require RMB; an invalid scale or incompatible destination produces a local `MEASUREMENT_MISMATCH`, removes the computed cell value, and leaves that V4 period unresolved.

The non-unit regression converts revenue and all opening/closing operating-working-capital stocks from `RMB_10K` to RMB. It demonstrates a converted FY2020 D3 of `999925`, working-capital charge of `30000`, and a V4 observation accepted by the existing consumer with RMB units.

### 3. Legal fact reuse is deduplicated; conflicts are local mismatches — closed

Root cause previously: `ACQUISITION_MODULE`.

The projection canonicalizes a repeated field at the frozen component, role, field, clock, and responsibility boundary. Identical occurrences collapse to one verified observation, so the FY2020 operating-cash-flow fact can feed both its deterministic cell and D4. A conflicting duplicate becomes `MEASUREMENT_MISMATCH`, invalidates the affected construction, and leaves only the affected V4 period unresolved; it is not arbitrarily selected or converted to `UNKNOWN`.

### 4. Component responsibility identity is stable — closed

Root cause previously: `ACQUISITION_MODULE`.

Multi-source validation binds each `component_id` to one `(component_role, responsibility_unit_id, perimeter_id)` tuple. The test rejects a role or responsibility-unit reassignment of `CORE`, while allowing different components to share a consolidated-report perimeter. This preserves the intended distinction among mature core, non-core real estate, and named growth cohorts.

## Evidence

- The two-report synthetic fixture continues to bind each raw fact to its authorized annual report and accepts a FY2019 opening balance disclosed by the FY2020 report.
- The baseline construction still yields owner cash `70`, non-core sum `10`, reconciliation residual `0`, signed stock delta `5`, and invested-capital return `0.15`.
- Missing and mismatched facts remain local and are never converted to zero.
- The focused suite completed successfully:

```text
.venv/bin/python -m pytest -q tests/test_enterprise_outcome_multi_source_acquisition.py tests/test_outcome_measurement_acquisition.py tests/test_enterprise_judgment_round5_v3_preoutcome.py tests/test_enterprise_judgment_round6_transfer_utility.py tests/test_enterprise_judgment_round8_express.py tests/test_enterprise_judgment_round9_appliance.py tests/test_outcome_measurement_settlement_adapter.py tests/test_working_capital_model.py tests/test_financial_driver_bridge.py

151 passed, 2 skipped
```

## Remaining bounded limits

- Public reports still do not provide Qilianshan project-level volume, operating cash, maintenance capital, or independently measured invested capital. Those components must remain conditional in the Course 2C training contract; no module can infer project ROIC from their absence.
- Consumer projection produces source-bearing inputs only. It is not a normal-earnings model, V4 candidate, valuation, or investment authorization.

## Acceptance gate

The four material acquisition defects are closed. Course 2C may now freeze its preregistration, fairness register, v2 contracts, and outcome custody request. No FY2018+ outcome may be opened until the two arm Episodes have completed contract binding.
