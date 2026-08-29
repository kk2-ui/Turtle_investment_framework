# CN Property Services FY2025 Industry Learning Block

This directory contains a report-preparation industry reference class for China Overseas Property Holdings (`HK:02669`). It turns the mature property-services research into an `IndustryLearningBlock` that can be compiled by `scripts/industry_underwriting_context.py`.

## Investor use

The block prevents a company report from treating property services as one homogeneous market. It separates four economic interfaces:

1. the shrinking developer-to-new-project feeder;
2. mature residential operations as the recurring earnings base;
3. public and institutional services as conditional growth exposed to tenders, mobilization, renewal and collection;
4. smart engineering as project optionality exposed to customization, acceptance, contract assets and cash collection.

The industry judgment is directional: the profit pool is migrating from incremental new development toward stock operations and adjacent services. The company judgment remains conditional. Public sources do not establish Zhonghai's project-level margin, invested capital, cumulative cash recovery or independent action effect.

## Peer policy

Peers are admitted by mechanism role and economic boundary, with no fixed peer count. China Merchants Property Operation & Service, Shenzhen SDG Service and Poly Property each contribute a different public-service or developer-ecosystem reference. China Resources Mixc Lifestyle Services is retained as a near miss because its commercial-management brand and tenant ecosystem can alter density, acquisition cost and margin; its city-space margin must not be copied to Zhonghai.

Revenue or market-cap similarity alone is prohibited as a peer rule.

## Source boundary

The JSON only uses facts and official links already present in these two read-only research papers:

- `feat-q1-02669-revision-20260811/research/02669/q1_1_f_revision_20260811/industry_outlook_research_20260813.md`
- `feat-q1-02669-revision-20260811/research/02669/q1_1_f_revision_20260811/city_public_cohort_and_platform_return_research.md`

No network acquisition was performed for this block. The `source_register` preserves the official source URLs from those papers, while `evidence_refs` keep compiled claims traceable to the register.

## Compile

```bash
python scripts/industry_underwriting_context.py \
  --company-id HK:02669 \
  --company-name "China Overseas Property Holdings" \
  --cutoff-at 2026-08-13T23:59:59+08:00 \
  --knowledge-cutoff-at 2026-08-13T23:59:59+08:00 \
  --industry-block docs/development/research/industry_learning_blocks/CN_PROPERTY_SERVICES_2025/01_industry_learning_block.json \
  --output /tmp/cn02669_industry_underwriting_context.json
```

A `READY` context is expected from this block. `BOUNDED` would still be report-consumable under the compiler contract; it must localize an unresolved field rather than block the report or turn every unknown into a no-judgment conclusion.
