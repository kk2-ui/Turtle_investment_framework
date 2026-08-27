# Execution Amendment: Provider Substitution Before Generation

The first execution attempt under `00_PAIRED_RUN_CONTRACT.md` terminated at
Anthropic authentication with HTTP 401. The repository credential is invalid.
No arm was generated, no evidence packet entered a model context, and no arm
output exists to select, repair, or discard.

To complete the already-frozen comparison with an available authenticated
runtime, the following execution fields replace only the provider/model fields
in the original contract:

- Runtime: `codex exec --ephemeral --ignore-rules --ignore-user-config` in an
  empty temporary working directory.
- Model: `gpt-5.6-sol`.
- Reasoning effort: `high`.
- Sandbox: read-only.
- Tool instruction: the model is explicitly prohibited from calling tools.
- Runtime acceptance: the JSON event stream must show no tool call. Any tool
  call invalidates that arm and ends the experiment without a semantic retry.
- Maximum output tokens: governed by the same fixed response-length
  instruction because this CLI does not expose a per-call output-token flag.
- Provider retries: no coordinator retry after a generated answer.

The case, cutoff, source packet, shared task, shared system instruction, arm
difference, blindness, review criteria, two-primary-call limit, one-review-call
limit, excluded evidence, and acceptance standard remain unchanged.

This amendment is frozen before any successful primary generation. The failed
Anthropic authentication attempt is reported as one failed transport attempt,
not as a model call and not as evidence about either prompt arm.
