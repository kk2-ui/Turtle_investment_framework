# Forecast prospective and holdout controls v1

Status: implemented in the historical-training worktree; synthetic control
evidence only. This document does not grant CJO, valuation, report, or
investment authority.

## Purpose

The forecast lane distinguishes a historical `MODEL_MEMORY_MITIGATED` pilot
from evidence of forward generalisation. A Company State Forecast becomes a
prospective shadow only through a new immutable V3 shadow receipt. A candidate
method change becomes eligible for later review only when its paired baseline
was pre-registered against a canonical company-and-time holdout.

## Prospective Company Shadow v3

`turtle-prospective-shadow-episode.v3` is a CompanyStateForecast object, not
the existing R05 mechanism-signal probe. It binds the exact frozen Forecast,
Decision Contract, Outcome Measurement Contract, and the designated custodian.
V4 and V5 also bind their frozen preforecast evidence receipt; V5 additionally
binds its Acquisition Scope.

The receipt has exactly one `resolution_calendar` entry for each of the one,
three, and five-year windows. Each due time must follow the corresponding
Measurement Contract outcome-period end and be future at registration. Every
bound Measurement Contract outcome-period end must itself still be in the
future when the shadow is registered; a later arbitrary due date cannot turn
a historical replay into prospective evidence. The Forecast must already be
frozen before registration. If a V3 shadow exists, outcome access cannot open
before the final due time.
Registration rejects an already-authorized, observed, or settled forecast.
Historical Forecasts without this shadow retain their existing outcome access
path and cannot be retroactively represented as prospective evidence.

R05 remains an independent signal probe. Its static source allowlist is first
stored immutably in `judgment_pit_prospective_signal_source_freezes`; its
shadow must then cite that exact receipt at a strictly later registration time.
This does not turn a signal probe into a CompanyStateForecast or a valuation
input.

## Canonical company-and-time holdout binding

Pairing V2 replaces caller-authored `training_company_ids` / cutoff assertions
with a canonical company-and-time request. Pairing V3 is the learning-transfer
form: before outcome access, the controller resolves one `HISTORICAL_HOLDOUT`
episode and its historical-training lane from `judgment_training_programs` and
`judgment_training_episodes`. It requires:

- active program, `COMPANY_AND_TIME` axis, sealed historical PIT provenance;
- both effective and recorded immutable method-freeze times before pairing;
- exact company/cutoff and enhanced method-version match;
- one or more unique `MODEL_UNCERTAIN` Measurement Contract cells.
- for V3, an unseen economic `company_cluster_id` and non-overlapping frozen
  half-open outcome-resolution windows for the holdout and every training
  episode.

The append-only V3 pairing stores the resolved economic `company_cluster_id`,
the historical training clusters and frozen outcome windows, and each cell's
frozen `outcome_period_end`. Candidate `EVIDENCE_PRIORITY` and
`RIVAL_HYPOTHESIS_METHOD` attributions must use Pairing V3 and may cite only
these pre-registered cells. A caller-authored legacy `holdout` object can no
longer support candidate method transfer. The V6 Forecast epoch adds the
immutable producing-method identity (`program_id`, method version, and both
method-freeze times); Pairing V3 must exactly reproduce all four fields rather
than treating a reused method-version string as identity. A V6 Minimal
Historical Episode may open independent custodian outcome access without any
pairing. A learning-transfer or decision-utility pairing must freeze before
outcome access; a new pairing after access is rejected, while
exact replay of an existing immutable pairing remains allowed. V1--V5 Forecasts
cannot be retroactively upgraded, and remain in the direct calibration or
coverage lane only. Direct calibration and coverage feedback remain separate
and retain no transfer claim.

Legacy programs without frozen `outcome_window_ends_at` values remain valid for
their existing V2 records and exact replays, but cannot produce a V3 learning
transfer pairing. The span metadata belongs to the existing training-program
truth; no caller-declared company list or cutoff proves this separation.

## Boundaries

These controls do not create a real forward shadow, open any outcome source,
settle a forecast, amend a CJO, create a BuyBand, or release a report. A real
prospective episode still needs a separately frozen forward Decision,
Measurement, source-evidence and custodian chain.
