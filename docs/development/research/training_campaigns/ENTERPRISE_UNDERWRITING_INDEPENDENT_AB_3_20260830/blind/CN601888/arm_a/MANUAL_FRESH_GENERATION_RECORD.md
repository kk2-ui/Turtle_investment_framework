# Manual Fresh Generation Record

- Artifact: `manual_episode_draft.json`
- Contract: `CN601888_INDEPENDENT_AB_3_BASELINE_CONTRACT.json`
- Generator: fresh Baseline Agent, working independently from the neutral source package and the episode schema/validator.
- Evidence boundary: only the baseline contract, its single allowed neutral pre-cutoff source package, and `scripts/enterprise_underwriting_episode.py` schema/validator were used.
- Runtime status: this is a manual fresh-agent generation produced because the standard provider runtime returned HTTP 401. It did **not** pass through the standard runtime and must not be represented as a standard-runtime generation.
- Leakage boundary: no post-cutoff outcome, market data, return, Enhanced-arm material, other campaign material, or prior arm result was used.
- Completion boundary: this record does **not** claim that the A/B comparison, campaign, or acceptance process is complete. The artifact remains a draft for the authorized downstream validation/review step.
- Repository action: no commit was created by this generation step.
