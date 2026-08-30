# Manual fresh generation record

- Artifact: `manual_episode_draft.json`
- Generator: fresh Enhanced Agent
- Generation mode: manual fresh generation after the configured provider returned HTTP 401; this artifact did **not** pass through the standard provider runtime.
- Read boundary: the Enhanced contract, its neutral pre-cutoff source package, `01_CHANNEL_CONTRACT_AND_CASH_RESPONSIBILITY_TREATMENT.md`, and the schema/validator portion of `scripts/enterprise_underwriting_episode.py` only.
- Outcome boundary: no post-cutoff result, price, return, Baseline arm, `00` material, other campaign, or campaign result was used.
- Treatment role: the treatment supplied research questions, evidence ordering, and conditional handling only; it was not treated as a fact about the target company.
- Full contract-binding check: `enterprise-underwriting-training-episode-validation.v1` returned `REVIEWABLE` with no findings; this does not substitute for the failed standard provider runtime.
- Status: manual draft for review and validation. It is not evidence that the standard runtime succeeded, and it does not establish that the A/B comparison is complete.
- Repository action: no commit was created for this generation.
