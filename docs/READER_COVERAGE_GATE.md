# Reader Coverage Gate

`reader_coverage.py` protects the reader layer when a valuation or return
module is repaired. The failure it addresses is specific: a full report is
reassembled as a short technical memo while arithmetic and structured ledgers
still pass.

## Required Reader Questions

The reader-facing document must explain, in company-appropriate language:

- what the business sells, who pays, and how money is made;
- historical/normal earnings or the applicable cash, NPI, FCF, asset, project,
  regulatory-capital, or pipeline route;
- how cash reaches ordinary shareholders, including minority claims,
  restrictions, debt, and entity control;
- the valuation and return route, the identity of each important price, and the
  primary decision return;
- the strongest counter-thesis and what could create permanent loss;
- monitoring metrics and upgrade/downgrade/termination triggers;
- evidence boundaries, assumptions, and explicit unknowns.

Each topic needs prose that connects multiple parts of the economic question.
A source list, field name, ledger ID, or technical appendix link cannot close a
topic. When a fact is unavailable, `UNKNOWN`/`未披露` is valid only when the
report explains the economic consequence of that unknown.

The reader body also rejects review-return panels, workflow statuses, internal
object IDs, and model identities such as `PRIMARY_ROUTE_UNKNOWN`, `P_LONG`, or
`P_XIRR_*`. Those identities remain available in the deterministic model and
technical appendix. Reader prose must translate them into the route, terminal
value, horizon, currency, tax, and investor consequence they represent. This
boundary deliberately continues to allow NAV, EPV, owner cash, audited facts,
and ordinary-language uncertainty.

## Archetype Routing

The validator reads `company_archetype.json` (or the valuation profile) and
changes the earnings-route cues without forcing one report template on every
company. A utility is checked for asset cash, maintenance and term; a
regulated financial institution for income, regulatory capital and
distributable cash; a property/asset case for rent, occupancy, project cash and
realisation constraints. The common reader questions remain stable.

## Lifecycle Hook

`report_completion.py` runs the gate for current archetype-aware runs. The
assembler runs it again on the actual reader text after compact memo rendering,
not only on chapters and the technical appendix. A blocked result is retained
as a draft and cannot be published. Legacy directories without archetype
context retain existing completion behavior until regenerated through the
current pipeline.

The JSON result uses `schemas/reader_coverage.schema.json`. It is a semantic
contract with material findings, not a score or byte/line target.
