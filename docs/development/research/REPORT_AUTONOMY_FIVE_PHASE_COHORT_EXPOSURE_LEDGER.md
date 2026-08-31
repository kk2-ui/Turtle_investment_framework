# Stage-5 cohort identity and exposure ledger

`scripts/report_autonomy_cohort_exposure_ledger.py` is the small local-only
control that precedes appliance / consumer-durables panel allocation.  It is
an exposure control, not a source registry, Pack compiler, candidate selector,
or outcome evaluator.

It records one canonical issuer identity (`issuer_id`, legal-entity identity,
listed-security identifiers, current name and aliases), the issuer's intended
side, and any known prior role:

| Prior role | Effect on a prospective test issuer |
| --- | --- |
| `PACK`, `TEACHER`, `HOLDOUT`, `TARGET`, or `CAMPAIGN` | Blocks `TEST_ACQUISITION` |
| No prior exposure in the ledger | May remain `TEST_ACQUISITION`; this is not selection or admission |

The only intended-side values are `PACK_BUILDING`, `TEST_ACQUISITION`,
`EXCLUDED`, and `UNASSIGNED`.  An issuer can have several historical exposure
records but exactly one intended side.  The validator rejects a legal-entity,
security-identifier, or normalized name/alias collision across issuer records,
and rejects an exposure referring to an unregistered issuer.  This catches a
renamed or differently coded issuer before it can be placed on both sides.

Security identifiers use the single local form `MARKET:SECURITY`. Case and
whitespace around `:` are canonicalized before collision checks; other forms
are rejected for curation rather than guessed into an equivalence. The
`exposures` collection must be an array—malformed values are invalid and are
never interpreted as an empty history.

The ledger accepts only opaque local references and declares the explicit
`LOCAL_ONLY_NO_OUTCOME_OR_PRICE` policy.  It never opens those references.
Consequently, a passing ledger only proves that the recorded identities are
disjoint at the feasibility stage; it does not establish source completeness,
an Industry Experience Pack, candidate eligibility, a frozen cohort, report
quality, or training utility.

Validate a prospective ledger with:

```bash
.venv/bin/python scripts/report_autonomy_cohort_exposure_ledger.py path/to/ledger.json
```

The appliance feasibility audit remains the authority for why no real panel is
yet frozen: [appliance / consumer-durables feasibility audit](REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_CONSUMER_DURABLES_PANEL_FEASIBILITY_AUDIT.md).
