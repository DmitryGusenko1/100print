# Acceptance #10 — 2026-10-21

Production transport: permanent [bridge #8](https://github.com/DmitryGusenko1/100print/issues/8).
API #6 runs on 127.0.0.1:8096 as a supervised child of ceo-orchestrator,
so no separate ceo-chatgpt-api unit is required on this installation.

ProductionCodexProvider uses the authenticated ceoorch CLI, gpt-6.1-sol,
strict JSON schemas, a 180-second per-call timeout and bounded concurrency.
Live deterministic mode is rejected. CLI failures never become mock recommendations.
Allowed inference working directories are /opt/ceo-orchestrator and its own
ai-business-brain worktree. Tools are disabled, sessions ephemeral, raw inference
logs discarded; memory contains structured analytical artifacts only.

Project instructions: [copy this text](CHATGPT_PROJECT_INSTRUCTIONS.md).
Voice contract and the single spoken instruction: [Voice bridge](VOICE_BRIDGE.md).
CONTEXT retrieves server memory; ordinary messages create analysis tasks;
DECISION persists only a decision explicitly accepted by the user.
OUT includes request_comment_id for exact input/output correlation.

## Real acceptance — PASS

Exact requested pricing question was posted using the connected GitHub plugin:
[input](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6317842828).
Session: issue10-acceptance-v2; task: dc3ffdc8-9cda-4930-8878-8176691eb4ab.
[CHATGPT_OUT](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6318143052)
was published and independently read using the GitHub plugin. Verified result:

- provider=production-codex-v1, model=gpt-6.1-sol, demonstration=false;
- confidence=0.8; Sales, Finance, Marketing and Critic positions;
- explicit financial growth/margin tradeoff, counterarguments and Critic challenge;
- 83 checkpoints, 59 production calls, 68 persisted memory artifacts;
- all Council rounds 0–6 and analytical/v1 present;
- API #6 returns the identical full result; GitHub request_comment_id matches input;
- attempts=2 because of the deliberate crash; all 15 pre-crash checkpoints unchanged;
- orchestrator, watcher and worker active/enabled; zero duplicate bridge tasks.

The recommendation is to preserve base prices and run a controlled, bounded
experiment after collecting unit economics and defining stop criteria, rather
than automatically agree to a blanket 15% cut. Missing company data is explicit.

The earlier issue10-acceptance request failed closed on a Codex process error;
it remains an honest failed receipt in bridge history.

During v2 execution, only the own ceo-orchestrator MainPID was killed after
15 durable checkpoints. Systemd restarted it automatically; the same task
resumed, and all 15 checkpoint fingerprints, results and metadata were unchanged.
The own watcher was also restarted; durable intake mappings and cursor survived.

Memory was independently read through the GitHub plugin from a new session:
[CONTEXT response](https://github.com/DmitryGusenko1/100print/issues/8#issuecomment-6317906767).
It contains the accepted technical decision from issue10-memory-acceptance.
No commercial price-cut decision was invented or saved as accepted.

Verification command (read-only):

```sh
.venv/bin/python scripts/verify_production.py --session issue10-acceptance-v2 --snapshot data/issue10-v2-before-restart.json
```

Validation: 36 tests passed in separate batches: 22 API/domain/PostgreSQL/progress,
8 bridge/provider, 1 API service restart, and 5 runtime integration tests.
The initial discovery run was interrupted before runtime tests because a long
production task occupied the single queue worker; those tests were then run on
an idle queue. The real acceptance verifier passed again after the runtime crash
recovery test. git diff --check passed.

Run runtime crash tests separately from a long production analysis: the queue
has one active business task, and short echo-test deadlines assume an idle queue.

## Limits

The verified client is the GitHub plugin. Actual audio/Voice UI execution cannot
be exercised from this VPS. The single spoken instruction assumes GitHub tools
are already connected and available in the selected chat; project instructions
cannot enable a plugin or bypass client permission prompts. Therefore actual
Voice-client acceptance remains unverified, rather than a claimed audio E2E pass.

A single model supplies isolated departmental roles, not independent model vendors.
No company margin/demand data was supplied; financial advice is conditional.
Transient upstream errors, authorization expiry and long inference latency remain
possible. Bounded retries preserve checkpoints and fail closed when exhausted.
GitHub does not offer an exactly-once POST key: confirmed replies recover by marker,
but an ambiguous HTTP result cannot provide a mathematical exactly-once guarantee.
