# Expert-correction training memory

> schema: `expert-correction-training-memory.v1`
> authority: `TRAINING_MEMORY_ONLY_NOT_TARGET_COMPANY_EVIDENCE`

This memory changes question order, rival checks, conditional treatment and price/route identity only.
It is not evidence about the target company, cannot be cited in the target Episode, and cannot supply a valuation, price or action.

## Portable correction rules

### ECORR:NEW_GROWTH_IS_NOT_MATURE_RETURN

- Rule: Implementation proves implementation only; promote growth into base owner economics after customer adoption, unit economics and cash absorption close on the same responsibility unit.
- Apply when: A company reports new projects, stores, capacity, acquisitions, products or service cohorts whose mature economics are not separately observable.
- Do not apply when: The new activity has contractually fixed economics, immediate customer payment and immaterial incremental capital, with direct issuer evidence for each condition.
- Next-case probe: Reconstruct one mature cohort from customer acceptance through unit economics, working capital and cumulative cash before underwriting the portfolio.
- Decision surfaces: BUSINESS_ENGINE, NORMAL_EARNINGS, OWNER_CASH, VALUE_ROUTE, REVERSAL_EVIDENCE

### ECORR:CONSOLIDATED_CASH_IS_NOT_ORDINARY_SHAREHOLDER_CASH

- Rule: Balance-sheet cash becomes ordinary-shareholder value only through a responsibility-matched ownership and realization bridge; uncertainty narrows recognition but does not automatically make the cash worthless.
- Apply when: Material cash sits in subsidiaries, regulated entities, joint structures or groups with related-party balances and distribution frictions.
- Do not apply when: The cash is held directly by the listed parent, unrestricted, wholly attributable and repeatedly distributed or deployed at observable adequate returns.
- Next-case probe: Map cash-holding entities, ownership, restrictions, taxes, upstream history, special-return funding, post-payment balances and project-batch collections; reconcile each source against ordinary distributions before assigning a cash range.
- Decision surfaces: OWNER_CASH, PERMANENT_LOSS, VALUE_ROUTE

### ECORR:PARENT_SYSTEM_HAS_SUPPORT_AND_EXTRACTION_CHANNELS

- Rule: A parent system can improve customer access and financing while simultaneously constraining ordinary-shareholder cash; never net the two mechanisms before tracing each to owner economics.
- Apply when: The issuer depends materially on a parent, platform, government network, franchise system or related customer group.
- Do not apply when: Transactions are immaterial and the target has independent customers, financing, allocation and cash distribution.
- Next-case probe: Build two arrows from the relationship: one to operating advantage and one to cash or governance claims, then test both with separate evidence.
- Decision surfaces: CENTRAL_THESIS, BUSINESS_ENGINE, MANAGEMENT_AND_CAPITAL_ALLOCATION, OWNER_CASH, STRONGEST_RIVAL

### ECORR:AGGREGATE_PROXY_IS_NOT_COHORT_RETURN

- Rule: A proxy inherits the responsibility unit, period and numerator-denominator definition from which it was calculated; never promote it to a narrower cohort without reconciliation.
- Apply when: Only aggregate changes are disclosed while the thesis depends on a particular project, product, acquisition or segment return.
- Do not apply when: The enterprise is economically single-engine and the disclosed capital and earnings map directly to the claimed unit across a mature period.
- Next-case probe: State the proxy's exact responsibility boundary and ask whether a different component or period could produce the same aggregate result.
- Decision surfaces: BUSINESS_ENGINE, NORMAL_EARNINGS, OWNER_CASH, VALUE_ROUTE

### ECORR:ARITHMETIC_PRICE_IS_NOT_ACTION_PRICE

- Rule: Arithmetic does not authorize a price, but uncertainty does not excuse route paralysis: select the best-current economic terminal, bind the research price to that route, and expose rival terminals and reversal evidence separately.
- Apply when: A valuation depends materially on future market recognition, a chosen terminal multiple, a catalyst or an uncertain distribution route.
- Do not apply when: The receipt is contractually fixed or liquidation-bound and needs no competing terminal judgment; if no economically defensible route can be bounded, do not invent one and keep the action price unknown.
- Next-case probe: For every quoted price, name the operating cash, shareholder receipt, terminal mechanism, required return and strongest rival route; explain why the selected base route is currently better.
- Decision surfaces: VALUE_ROUTE, PRICE_IDENTITY, REVERSAL_EVIDENCE

### ECORR:ACTION_HIERARCHY_DOES_NOT_REPLACE_DERIVATION

- Rule: An executable action hierarchy and a challengeable economic derivation are both required: keep a concise bridge from business components through normal earnings and accessible cash to value, return and action price.
- Apply when: A report combines several business engines, normalization adjustments, cash-accessibility judgments, sensitivities or competing value routes.
- Do not apply when: A compact single-engine bridge already exposes every material operating, cash, terminal and return assumption in the reader-facing report.
- Next-case probe: Ask a blind investor to reconstruct the material profit and cash bridge, identify the dominant sensitivity contribution, and reconcile the selected terminal to the action price without opening model artifacts.
- Decision surfaces: BUSINESS_ENGINE, NORMAL_EARNINGS, OWNER_CASH, VALUE_ROUTE, PRICE_IDENTITY, SOURCE_BINDING

### ECORR:LOCAL_UNKNOWN_DOES_NOT_ERASE_THE_ENTERPRISE

- Rule: Propagate an unknown only through the claims and components that depend on it; retain independent enterprise economics unless the residual can dominate survival, owner cash or value.
- Apply when: A diversified or multi-engine company has one material but separable evidence gap.
- Do not apply when: The missing item controls solvency, financing continuity, the dominant earnings engine or the only credible realization route.
- Next-case probe: Draw the unknown's dependency path and bound its maximum effect before deciding whether it is local or whole-company.
- Decision surfaces: CENTRAL_THESIS, BUSINESS_ENGINE, NORMAL_EARNINGS, OWNER_CASH, PERMANENT_LOSS, VALUE_ROUTE

### ECORR:PERMANENT_LOSS_CAN_BE_SLOW_VALUE_DESTRUCTION

- Rule: Permanent loss includes slow per-share value destruction through margin erosion, cash absorption and low-return retention even when solvency and dividends remain intact.
- Apply when: A mature, cash-rich or state-linked company appears financially safe but retains material capital or expands into weaker economics.
- Do not apply when: The company is executing a credible liquidation or distribution path that returns capital despite operating contraction.
- Next-case probe: Separate survival from per-share owner value, then trace every retained unit into incremental return, accessible cash or irreversible loss.
- Decision surfaces: OWNER_CASH, PERMANENT_LOSS, STRONGEST_RIVAL

### ECORR:EVIDENCE_MUST_BIND_NEAR_THE_DECISIVE_CLAIM

- Rule: Bind primary evidence beside each decisive factual premise and keep inference and model output in separate language; a writing repair must not silently change economics.
- Apply when: A report relies on cash accessibility, cohort economics, related-party transmission, permanent loss or route identity that a reader could otherwise mistake for disclosed fact.
- Do not apply when: A compact local table already maps each decisive premise unambiguously to a primary source and clearly labels inference and calculation.
- Next-case probe: Ask a blind reader to trace the central thesis, strongest rival, owner cash, permanent loss and route premise directly to nearby primary evidence.
- Decision surfaces: SOURCE_BINDING, CENTRAL_THESIS, STRONGEST_RIVAL

## Conditional investment principles

### CPRINCIPLE:SEPARATE_ASSET_EARNING_GROWTH_VALUE — Separate current earning power from growth value

- Principle: Value current assets and earning power separately from growth; growth enters only when incremental economics and owner realization are supportable.
- Economic object: asset value, earning-power value and growth value
- Apply when: A thesis combines mature operations, excess assets and new growth components.
- Mechanism: Mature earnings, distributable assets and reinvested capital reach owners through different cash and competitive mechanisms and therefore require separate evidence and routes.
- Required target evidence: normalized mature earnings; asset ownership and realization; incremental return and capital absorption; ordinary-shareholder distribution or reinvestment path
- Common misuse: Adding cash, current earnings and an assumed growth premium into one blended value without checking overlap or realization.
- Counterconditions: A liquidation case may make asset realization primary and ongoing earnings secondary.; A young single-engine company may lack mature earning power and require a bounded option treatment rather than a false three-part precision.
- Downstream use: Assign each component to base, conditional, stress or excluded valuation routes without averaging incompatible price identities.
- Disconfirming observation: The supposedly separate components are economically inseparable or double count the same cash flow.

### CPRINCIPLE:RETENTION_VALUE_REQUIRES_INCREMENTAL_RETURN — Retained capital is valuable only through incremental owner economics

- Principle: Retained earnings are not automatically worth their accounting amount; their value depends on incremental return, cash conversion and ordinary-shareholder realization.
- Economic object: capital allocation and growth value
- Apply when: A company retains material owner earnings, expands capacity, acquires businesses or builds new service cohorts.
- Mechanism: Retention creates per-share value only when the resulting earnings and accessible cash exceed the relevant capital requirement after all absorption.
- Required target evidence: retained-capital uses; matched incremental earnings; working-capital and integration absorption; per-share distribution or value realization
- Common misuse: Treating every retained unit as additional value or using revenue growth as proof of adequate incremental return.
- Counterconditions: Temporary defensive liquidity can preserve survival value without generating a normal growth return.; A regulated utility can require a rate-base and allowed-return analysis instead of a generic cohort test.
- Downstream use: Exclude unproved retention from base growth value, reflect current total capital absorption in financing pressure and specify promotion tests.
- Disconfirming observation: Mature investments repeatedly earn and distribute adequate incremental owner cash on matched capital.

### CPRINCIPLE:CASH_REQUIRES_CLAIM_AND_REALIZATION — Cash value follows the shareholder claim and realization path

- Principle: Cash protects ordinary shareholders only to the extent that ownership, restrictions, allocation and distribution make it economically accessible.
- Economic object: ordinary-shareholder cash
- Apply when: Material cash is held across subsidiaries, financial units, joint structures or related-party networks.
- Mechanism: Legal-entity ownership, reserves, regulation, taxes, non-controlling claims, receivables and capital allocation determine whether consolidated cash becomes ordinary-shareholder value.
- Required target evidence: cash-holding entities and ownership; restrictions and tax friction; related balances; historical distributions and capital allocation; special-return funding and post-payment balances; project-batch collections reconciled to ordinary distributions
- Common misuse: Counting all consolidated cash at full value, counting parent and consolidated cash twice, or assigning zero because exact upstreamability is missing.
- Counterconditions: Direct unrestricted parent cash with repeated distribution can justify high recognition.; Regulated or deposit-funded financial cash requires its own capital and liquidity boundary rather than an industrial cash formula.
- Downstream use: Use a cash-accessibility range in owner cash, permanent loss and value routes without allowing the range to become a legal-entitlement claim.
- Disconfirming observation: Actual entity disclosures or repeated distributions establish a materially different accessibility boundary.

### CPRINCIPLE:PRICE_IDENTITY_FOLLOWS_ECONOMIC_ROUTE — Price identity follows the economic route

- Principle: A price is meaningful only after identifying the owner-cash, asset-realization or market-terminal route that can deliver it.
- Economic object: valuation route and margin of safety
- Apply when: Several reverse prices, value routes or terminal assumptions coexist.
- Mechanism: Different routes answer different questions and bear different realization risks; numerical precision cannot reconcile incompatible mechanisms.
- Required target evidence: route-specific cash flows; timing and terminal mechanism; realization evidence; consistent entry and exit assumptions
- Common misuse: Averaging route prices, promoting a fixed-terminal reverse calculation to action status, or confusing a stress boundary with a base value.
- Counterconditions: A contractually fixed receipt can make a reverse price directly executable within its terms.; A liquidation route can supersede operating EPV when the asset-distribution mechanism is actually underway.
- Downstream use: Keep route-specific prices separate, choose the best-current defensible route for the explicit research price, and leave the action price unresolved only when no route can be economically bounded.
- Disconfirming observation: New evidence makes a rival route more defensible or shows that no route can support an explicit research price.

### CPRINCIPLE:PERMANENT_LOSS_IS_NOT_BANKRUPTCY_ONLY — Permanent loss includes slow per-share value destruction

- Principle: Permanent loss is the impairment of owner purchasing power and per-share value, not merely insolvency or price volatility.
- Economic object: permanent loss
- Apply when: A financially stable company retains capital, faces mature-margin pressure or expands into weaker economics.
- Mechanism: Low-return retention, inaccessible cash, working-capital absorption and competitive erosion can destroy owner value while the enterprise survives.
- Required target evidence: mature economic direction; retained-capital return; cash accessibility; per-share distribution and dilution
- Common misuse: Equating survival, cash balance or continued dividends with low permanent-loss risk.
- Counterconditions: A credible liquidation and distribution plan can preserve owner value during operating decline.; Temporary countercyclical retention can protect earning power if later release and returns are observable.
- Downstream use: Include slow erosion and opportunity-cost paths in downside treatment and required margin of safety.
- Disconfirming observation: Retained capital repeatedly converts into adequate per-share owner cash or durable earning power.

### CPRINCIPLE:INDUSTRY_STRUCTURE_BOUNDS_MANAGEMENT — Industry structure bounds management quality

- Principle: Management skill matters through the strategic and capital-allocation choices available inside an industry's customer, competition and profit-pool structure.
- Economic object: industry future and company adaptation
- Apply when: The thesis credits management, a parent platform or execution with overcoming price, customer or competitive pressure.
- Mechanism: Strong execution can improve position and allocation, but cannot by itself repeal weak bargaining power, poor unit economics or structural capital absorption.
- Required target evidence: customer job and bargaining power; competitive response; company-specific adaptation; unit economics and cash transmission
- Common misuse: Using biographies, awards, project wins or parent reputation as direct evidence of durable economics.
- Counterconditions: A demonstrable business-model change can alter the company's exposure to the old industry structure.; A legally protected franchise can make regulation rather than conventional competition the decisive bound.
- Downstream use: Make industry and management judgments meet in company-specific normal earnings, owner cash and reversal conditions.
- Disconfirming observation: The company sustains superior unit economics and cash through an adverse competitive period on a responsibility-matched basis.

### CPRINCIPLE:LOCALIZE_UNCERTAINTY_AND_BIND_EVIDENCE — Localize uncertainty and keep the reader able to verify the thesis

- Principle: A material unknown limits the claim that depends on it; the report must still make the remaining enterprise judgment and bind decisive facts near that judgment.
- Economic object: decision-useful research under uncertainty
- Apply when: One component lacks exact economics or cash attribution while other enterprise mechanisms remain independently supportable.
- Mechanism: Component boundaries prevent unsupported propagation, while nearby evidence lets the reader distinguish observation, inference and model output.
- Required target evidence: dependency path from unknown to decision; bounded residual; primary-source anchors for decisive premises; clearly labelled inference and model output
- Common misuse: Ending the whole case as unknown, filling the gap with precision, or hiding all sources in a remote bibliography.
- Counterconditions: A missing solvency, financing or dominant-engine fact can legitimately block the whole treatment.; A concise local source table is sufficient when each claim-to-source mapping is unambiguous.
- Downstream use: Continue normal earnings, owner cash, permanent loss and value judgments that remain independent; downgrade only the affected route and state the reversal evidence.
- Disconfirming observation: The residual can dominate the whole enterprise or the cited source fails to support the decisive premise.

## Use boundary

On a later company, rebuild every fact and every economic link from that company's allowed cutoff sources.
If a rule's applicability evidence is absent, narrow or reject the analogy. Do not reward additional prose, caveats or fields;
the only useful change is a material improvement in the enterprise judgment or investment treatment.
