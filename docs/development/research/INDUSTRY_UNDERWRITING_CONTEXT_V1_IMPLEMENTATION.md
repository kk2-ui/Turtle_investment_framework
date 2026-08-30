# IndustryUnderwritingContext V1

## 1. Purpose

`IndustryUnderwritingContext` is the compact industry read model available
before company underwriting and Golden Report synthesis. It answers the
practical context problem without putting whole IndustryLearningBlock files,
the mechanism library, and every peer filing into one model prompt.

It projects four existing sources:

1. `IndustryLearningBlock v1/v2`: epochs, mechanism arenas, archetypes,
   heterogeneous company conditions, peers, near misses, unresolved questions,
   and source pointers;
2. locator-backed official industry observation ledgers that have passed
   `industry_context_acquisition.py` against an archived raw source package;
3. `scripts/industry_knowledge.py`: matched mechanism cards and the company
   fields needed to test them, read through the existing public API;
4. the company's competitive arena: customer task, product scope, overlap
   dimensions, exposure, and any explicitly recorded members.

The projection does not write a new database, copy mechanism cards, create a
company fact, or produce an investment conclusion. Canonical facts remain in
their original objects and are referenced through `source_objects[]` and
`evidence_refs[]`.

## 2. Stable API

```python
from scripts.industry_underwriting_context import (
    compile_industry_underwriting_context,
    validate_industry_underwriting_context,
)

payload = compile_industry_underwriting_context(
    company={
        "company_id": "CN:600585",
        "company_name": "Anhui Conch Cement",
        "cutoff_at": "2018-04-30T23:59:59+08:00",
        "knowledge_cutoff_at": "2018-04-30T23:59:59+08:00",
        "industry_keys": ["cement"],
    },
    industry_learning_blocks=[
        "docs/development/research/industry_learning_blocks/"
        "CN_CEMENT_2014_2018/04_industry_learning_block.json"
    ],
    official_industry_observations=[
        "docs/development/research/industry_learning_blocks/"
        "CN_CEMENT_2014_2018/60_official_industry_context_observations_v1.json"
    ],
    competitive_arena=arena_payload,
)

assert validate_industry_underwriting_context(payload)["state"] == "REVIEWABLE"
```

Full function signature:

```python
compile_industry_underwriting_context(
    *,
    company: Mapping[str, Any],
    industry_learning_blocks: Iterable[Mapping[str, Any] | str | Path] = (),
    official_industry_observations: Iterable[Mapping[str, Any] | str | Path] = (),
    competitive_arena: Mapping[str, Any] | None = None,
    industry_keys: Iterable[str] = (),
    mechanism_keys: Iterable[str] = (),
    knowledge_dir: str | Path | None = None,
    industry_knowledge_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]

validate_industry_underwriting_context(payload: Any) -> dict[str, Any]
```

`competitive_arena` accepts an arena object, a V5 object containing
`competitive_arena`, or a V3 object containing `competitive_arenas[]`.
`industry_knowledge_context` is optional: when absent, the compiler calls
`industry_knowledge.read_industry_knowledge_context()` with the supplied
industry and mechanism keys. Historical PIT callers must either set
`pit_mode=true` or pass an explicitly admitted PIT context; the compiler will
not silently open the current global mechanism library in PIT mode.

## 3. Output Contract

The default output filename is `industry_underwriting_context.json`. Its schema
is `schemas/industry_underwriting_context_v1.schema.json`.

```text
company_identity
industry_value_chain {stages, customer_jobs}
structural_epochs[]
industry_drivers {demand, supply, competition, regulation}
profit_pool_outlook
company_archetype_exposure
representative_peers[]
near_misses[]
candidate_main_paths[]
strongest_counter_thesis
company_verification_fields[]
evidence_refs[]
knowledge_time
source_objects[]
coverage {available, bounded}
```

Peers are selected by recorded mechanism-arena overlap and are not capped at
two or three companies. A company with a material scope/control break or no
recorded arena overlap remains a `near_miss`; it is not discarded and is not
misrepresented as a comparator.

Driver grouping uses explicit categories when supplied and otherwise indexes
the source text into demand, supply, competition, and regulation buckets.
Validated official observations contribute their declared, reviewable
`profit_pool_effect` and economic interpretation; the compiler combines those
bounded effects into the Context direction and adds an official-evidence
candidate path. This is still a reference-class projection: the Golden Report
synthesizer must form its own company-specific exposure and adaptation judgment
from target-company evidence.

## 4. Sparse Context Is Non-Blocking

`context_status` has two report-consumable values:

- `READY`: every core context surface has support;
- `BOUNDED`: one or more surfaces are missing or unresolved.

Both have `report_use.non_blocking=true`. Sparse input still yields a candidate
main path that names the missing transmission and the company evidence needed
to resolve it. It does not create a new `NO_PRIMARY` gate or stop the rest of
the company report.

## 5. CLI

```bash
.venv/bin/python scripts/industry_underwriting_context.py \
  --company-id CN:600585 \
  --company-name "Anhui Conch Cement" \
  --cutoff-at 2018-04-30T23:59:59+08:00 \
  --industry-block docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/04_industry_learning_block.json \
  --official-industry-observation docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/60_official_industry_context_observations_v1.json \
  --competitive-arena docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json \
  --output industry_underwriting_context.json
```

Omitting `--output` uses `industry_underwriting_context.json` in the current
directory. The CLI writes only the derived object; it does not modify any input
block, mechanism card, EnterpriseUnderwritingEpisode, or report handoff.
