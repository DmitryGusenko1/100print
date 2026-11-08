# Issue 19 — dependency correction from issue 20 (2026-11-08)

Bridge implementation, artifact/replay checks and offline tests can resume now.
A Telegram token is not a prerequisite for those independent tasks. Paperclip
registration is also not required. No bridge work or acceptance is claimed by
issue 20. Only Telegram integration and real inbound E2E depend on the required
bot credential and subsequent gateway validation.

Issue 20 expanded the permitted project settings search: one unique token,
getMe=hundredprintbot; no WebToPrintISbot token. A single hidden local input is
prepared; see [current #18 update](ai-team/acceptance-2026-11-07.md).
The prior #19 WAITING_USER receipt is historical and must not suppress independent
bridge scheduling; replace it with the executing #19 worker's factual outcome.

## Historical report (superseded dependency rule)

# Issue 19 — prerequisite blocked

VPS check: 2026-11-07T22:10:21Z. Status: WAITING_USER; DoD incomplete.

Read saved progress (analysis, 10%), existing app/github_bridge.py,
docs/VOICE_BRIDGE.md and current issue #18 reports through the GitHub connector.
Latest #18 blocker: issuecomment-6713656513; worker receipt: issuecomment-6713665254.

Read-only Telegram getMe using only project config/telegram.env succeeded,
but the configured username is hundredprintbot rather than required WebToPrintISbot.
No token or owner identifier is included here. No polling, outbound messaging,
service restart or approval was performed. Existing unrelated changes were preserved.

Hermes inference evidence from #18 at 2026-11-07T22:07:53Z records one real
openai-codex model call; this is not bridge acceptance. No new bridge inference,
artifact, replay or restart acceptance is claimed. Existing bridge behavior remains
pending replacement and must not be represented as a verified Hermes integration.

Required action: replace CEO_TELEGRAM_TOKEN in the existing project-local
config/telegram.env with the token for @WebToPrintISbot, privately.
Executor readiness is telegram. Resume priority #18 model/Telegram readiness,
then implement and verify #19 without requiring Paperclip registration.
Progress remains analysis; no stage advancement for incomplete integration.
