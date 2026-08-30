# Baseline arm optional external-provider attempt

This filename is retained for provenance; it is not an active execution blocker.

- Contract: `contracts/CN601888_INDEPENDENT_AB_3_BASELINE_CONTRACT.json`
- Optional path attempted: explicit `--provider anthropic`
- Result: HTTP 401 authentication failure after the provider runtime retries.
- Economic consequence: none. No provider Episode was generated and the failed attempt did not alter the
  contract, source packet, Codex child response, or pre-outcome judgment.
- Current formal path: the independently generated fresh Codex response is stored in
  `manual_episode_draft.json` under its historical filename and finalized by `run --agent-response`.
- Formal completion: `TRAINING_EPISODE_COMPLETED / CODEX_FRESH_SUBAGENT`; the canonical persisted product is
  `enterprise_underwriting_episode.json`.

External-provider authentication is not required by the default Turtle training workflow.
