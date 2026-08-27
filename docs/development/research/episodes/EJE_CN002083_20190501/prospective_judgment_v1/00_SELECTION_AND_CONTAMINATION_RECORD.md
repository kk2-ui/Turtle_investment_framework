# CN:002083 Prospective Judgment Development Episode Selection

## Selection

- Company: `CN:002083` 孚日股份.
- Frozen cutoff: `2019-05-01T00:00:00+08:00`.
- Observation window: FY2019, due no later than `2020-05-01T00:00:00+08:00`.
- Existing frozen input: `EJE:CN002083:20190501` E0/E1 reconstruction.
- Episode class: `PROSPECTIVE_DEVELOPMENT_EPISODE`.
- Holdout/transfer status: `NOT_HOLDOUT / NOT_TRANSFER_VALIDATION`.

The company is selected before any FY2019 source discovery or body access. It
is the first existing real E1 episode whose next-period outcome remains unused
and whose cutoff packet exposes more than issuer-level revenue: repeated export
turnover, product and regional revenue/margin, physical sales volume, working
capital, operating cash, capital expenditure and borrowing are all measurable.
Reuse of the existing E1 is preferred to opening another cohort solely to make
completion easier.

The selection is not evidence that the company is comparable with R-62, the
cement block or the appliance rounds. It does not test Comparative or method
transfer.

## Contamination statement

The pre-outcome J0/J1 package was previously used to implement and verify the
E1 reconstruction path, so this is a development episode rather than an
unseen-company holdout. The coordinator has read the FY2014--FY2018 official
packet and the R-62 paired-run result. It has not searched for, opened, quoted
or extracted the FY2019 annual report, any FY2019 result source, price or
return before this freeze.

The outcome custodian will receive only the measurement contract and source
identity, not the pre-outcome judgments, scenarios or hypotheses.

## Why this episode can produce decision value

At the cutoff the company reported export and bedding growth, but external
sales margin compressed, operating cash fell below cash capital expenditure,
receivables and borrowing rose, and a named automation project carried a May
2019 commissioning objective. The next annual report can therefore
differentiate at least four economically distinct possibilities:

1. customer/market entry persists or weakens;
2. volume growth restores or fails to restore unit economics;
3. the named project is commissioned or remains unresolved;
4. operating progress converts or fails to convert into cash after capital
   absorption.

An observation that only fills fields but leaves all four treatments unchanged
will be recorded as `NO_MATERIAL_JUDGMENT_DELTA`, not as learning success.

