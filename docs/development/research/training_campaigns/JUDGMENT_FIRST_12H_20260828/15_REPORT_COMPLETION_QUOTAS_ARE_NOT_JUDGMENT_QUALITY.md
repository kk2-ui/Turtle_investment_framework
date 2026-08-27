# Report Completion Quotas Are Not Judgment Quality

## Decision

The active report pipeline no longer uses whole-report character count, global
numeric-line citation ratio, repeated search-call counts, or a fixed list of
valuation words as publication gates.

These were proxies for work volume, not tests of whether the report formed a
correct, useful, and falsifiable company judgment.

## Observed failure

Four supported paths rewarded defensive production:

- a concise report with all fifteen chapters and material judgments failed only
  because it had fewer than 20,000 substantive characters;
- a ten-row same-source table failed because one valid table source produced a
  low global anchor-to-numeric-line ratio;
- a chapter that answered its question with one high-authority search and one
  body fetch passed during writing but failed at completion for not repeating
  the calls;
- a deliberately withheld valuation failed unless it mentioned thirteen GG
  terms, even though the missing market input made those terms inapplicable.

Root cause: `ACQUISITION_MODULE + MODEL + REASONING + WRITING`.

Economic impact: the cheapest completion strategy was to add prose, duplicate
citations, repeat searches, and enumerate model terminology. None of those
actions improves the enterprise mechanism, owner-cash conclusion, permanent-
loss assessment, or valuation decision. In the withheld route, the keyword
gate could instead encourage a false impression that a valuation had been
performed.

## Runtime correction

- whole-report character count remains diagnostic only;
- a low global citation ratio is a warning, while unknown evidence sources and
  unsupported material claims remain blockers;
- a table-level source can support a same-source table without repeating the
  anchor on every row;
- each required external source type needs one eligible result or one recorded
  real unavailable attempt, not an arbitrary number of repeated calls;
- the fiscal-year requirement is frozen from the years actually available to
  the run instead of being imposed later as an unconditional two-year quota;
- Ch11 derivation is enforced by the structured valuation model and decision-
  reliability contracts, not by vocabulary matching.

## Boundaries retained

The change does not relax:

- chapter identity and non-empty body;
- claim-to-evidence binding for material numeric or narrative assertions;
- source normalization and rejection of unknown sources;
- required official-body sections, unless a real local unavailable condition
  has been recorded under the existing localized treatment;
- formula, model-input, decision-ledger, PIT, outcome-isolation, or permission
  checks.

A bare statement that information was unavailable still does not count as a
source attempt. Repeating a keyword or an anchor cannot repair an invalid
model or unsupported claim.

## Mechanical acceptance

- concise 15-chapter material report: no length block;
- ten-row same-source numeric table with one table source: accepted by the
  active quality path;
- unknown evidence source: still blocked;
- one eligible call per required external source type: accepted;
- no call and no recorded real failure: still blocked;
- real provider-unavailable attempt after official-body coverage: localized;
- withheld valuation without GG keywords: accepted when its structured state
  is valid;
- active valuation with a missing or inconsistent model: still blocked;
- independent review: `ACCEPT`, with `194 passed` across the two retained-
  boundary suites;
- targeted implementation suite: `130 passed`.

This correction does not claim that more concise prose is automatically
better. It makes information gain and decision quality the route to
completion, instead of paid repetition.
