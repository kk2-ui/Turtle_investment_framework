# Independent execution-interface repair review

## Decision: PASS

The pre-outcome v2 repair makes the same non-empty `responsibility_boundary`
obligation binding at all three relevant surfaces.  For a contract using
`enterprise-underwriting-economic-derivation-interface.v2`,
`build_fresh_subagent_task` loads a fresh copy of the Episode schema and adds
`responsibility_boundary` to each `driver_sensitivity_spec.required` list. Its
field definition is the non-empty-string definition. The rendered task text
also explicitly requires that boundary on every driver sensitivity, including
`UNKNOWN` and `PRESERVED` transmissions. The binding path selects the v2
validator requirement, and the focused parity test demonstrates that omission
produces `responsibility_boundary_required_by_interface_v2` while a non-empty
value clears that finding.

The frozen schema is not mutated: each fresh task begins from a newly loaded
schema and the added requirement is conditional on the v2 derivation
interface. The tests retain exact frozen-schema equality for non-v2 task
packets, and frozen legacy/v1 contracts remain validation/replay-only rather
than becoming fresh execution tasks.

Replacement execution artifacts can be isolated. The appliance preregistration
generator accepts an explicit `artifact_root` and derives every cell artifact
path, anonymous-review artifact path, and measurement-contract path from it;
the focused generator test covers the replacement-root projections.

Economic and experimental impact: the repaired interface permits a new,
separately frozen zero-attempt cohort to collect schema-conforming pre-outcome
episodes without mechanically invalidating responses that follow the supplied
task. It does not authorize reuse, retry, or amendment of the invalid cohort,
and it does not expose outcomes or create an investment conclusion.

No blocking `DATA_COVERAGE`, `ACQUISITION_MODULE`, `REASONING`, `MODEL`, or
`WRITING` issue remains within this repair scope. The four focused tests could
not be executed locally because `pytest` is not installed; their source-level
assertions directly cover the interface parity, frozen-schema preservation,
legacy replay boundary, and replacement-root isolation reviewed above.

PASS
