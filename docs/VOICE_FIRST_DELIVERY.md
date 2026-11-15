# Voice-first NEXUS delivery — 15 November 2026

## Baseline and scope

Development starts from `recovery/orb-first-home-20261110` at
`dcc96be3cfdeeb170ffe5d7710a5697a588e947c` ([PR #9](https://github.com/qaidhiaz6767-max/NEXUS-OSIS/pull/9)).
At audit, integrated `main` was `6baa5ea5a82e14b9109d779821513583a2550c92`.
PR #9 is the newer approved orb-only Home continuation. A fresh checkout had
no pre-existing local changes. Development uses `feat/voice-first-navigation`.
No existing branch was reset, merged or replaced.

Baseline: **118 Python tests**, **12 JavaScript tests** and the existing
orb/Home browser scenario passed before implementation. PR #8's 20-capability
blueprint was reviewed as a roadmap; this delivery concentrates on voice.

## What works

- Keep the approved Home and startup: greeting without orb, formation,
  initialization, readiness from the real Core, then orb-only Home. No cards,
  permanent composer, widgets or supporting Home copy were added. No CSS or
  orb markup changed. Demo mode retains its existing disclosure.
- Tap the orb to opt into voice. Final speech goes to the selected workspace;
  interim words and mixed final/interim hypotheses cannot dispatch commands.
  The small microphone buttons still prepare text for review without sending.
- Speak local navigation without Send or a model call: “NEXUS, open OSIS
  workspace”, “Open Academics”, “Switch to Development”, “Open ATLAS
  Headquarters”, “Buka workspace Finance”, “Go Home”, “Kembali ke beranda”.
  Bounded English/Indonesian variants include polite prefixes and akademik,
  pengembangan, keuangan, pribadi and riset. Unknown/compound commands and
  arbitrary URLs do not become navigation.
- Resolve destinations against the server-provided readable workspace list.
  Preserve the five primary six-function pages and seven canonical storage IDs:
  `osis`, `personal`, `academic`, `research`, `coding`, `finance`, `atlas`.
- During a reply or pending conversation request, tap the orb to cancel output
  and explicitly begin another listening turn. While listening, tap to stop.
  Escape stops voice/output. Navigation, hidden-tab changes and page exit stop
  active voice; destination pages never restart the microphone automatically.
- Listening pauses before speech output. The orb accurately reflects connecting,
  listening, thinking, speaking, error and idle states. Installed voice and
  English/Indonesian language selection remain available. Settings can disable
  spoken voice replies; responses then open in text conversation.
- Recognition and speech callbacks belong to a specific attempt. Cancelled or
  obsolete callbacks cannot append text, navigate, start playback, alter a newer
  orb state or overwrite the current response.
- Recover visibly from denied permission, connection failure, missing transcript,
  microphone startup timeout and stalled speech. Retry creates a fresh attempt.
  Three empty attempts stop rather than recording indefinitely. Missing speech
  support opens text; Command-K/Ctrl-K remains available on demand.
- Voice can prepare proposals, never approve them. Existing server permissions,
  expiring approvals, replay checks, SQLite records and Cognitive Core remain.

## Cancellation means stop waiting, not undo

`TurnGate` in `web/voice-session.js` owns the active client request and its abort
signal. Cancellation invalidates the turn before abort listeners run. Every
response, error, refresh and finalizer checks ownership before changing UI.
An old completion cannot clear a newer busy state or restart its microphone.

**The synchronous HTTP Core has no server cancellation endpoint.** A submitted
request can still complete and save conversation history or prepare an approval
proposal after the browser stops waiting. Cancellation does not delete a draft,
roll back a committed action, or revoke approval. Review history and the Approval
inbox before repeating an interrupted request. No cancelled request is retried
automatically. The browser test deliberately lets an interrupted request finish
and verifies that its proposal stays unapproved and its reply cannot replace the
current one.

The HTTP entry point treats a disconnected browser as a closed connection, not
an internal Core failure requiring a second response. No result is fabricated.

## Architecture and API compatibility

- `web/executive.js`: deterministic, bounded bilingual local routing. It returns
  a canonical ID or `home`; it cannot grant server permissions.
- `web/voice-session.js`: browser-independent turn ownership, final-transcript
  validation and explicit bilingual voice-stop parsing, with Node tests.
- `web/app.js`: existing UI integration, fresh recognition attempts, speech
  lifecycle, interruption, guarded command/refresh handling and fallback.
- `web/index.html`: existing Settings copy and one voice-output preference.
- `app.py`: allowlist `/voice-session.js`; handle expected disconnected clients.
  **No Core package, provider, API payload, schema or migration changed.**
- Existing synchronous `/api/chat`, `/api/state`, workspace, proposal and
  decision contracts are unchanged. Requests retain workspace parameters,
  same-origin headers and strict CSP. No external integration was added.

## Verification

Run from the repository root, using disposable synthetic data only:

```bash
python3 -m compileall -q app.py core.py nexus tests
python3 -m unittest discover -s tests -v
node --test tests/*.test.mjs
python3 tests/browser_voice_first.py
python3 tests/browser_orb_home.py
python3 tests/browser_redesign.py
python3 tests/browser_executive.py
python3 tests/browser_smoke.py
python3 tests/browser_csp.py
git diff --check
```

For local browsers, set `NEXUS_CHROMIUM` to an installed Chromium executable.
The new voice test otherwise uses Playwright's Chromium. Browser tests require
Playwright in a development environment; no new runtime dependency was added.
GitHub CI includes all Node tests and the synthetic voice browser suite.

Final local results: **118 Python tests and 21 JavaScript tests passed** (nine
new JavaScript tests). The new voice-first browser suite and existing orb/Home,
20-journey regression, executive startup, smoke and negative CSP suites passed.
The voice suite reported zero page errors, zero unexpected external requests,
zero microphone/speaker overlaps and no uncaught server disconnect errors.
Navigation preserved all seven workspace snapshots; business changes required
the separate manual approval exercised by the test. Compile, JavaScript syntax
and whitespace checks passed. Browser verification used Linux Chromium
156.0.8078.79 with mocked audio. The source commit and hosted CI results are
recorded on the pull request. New captures are written under ignored
`work/screenshots/voice-first/`; three reviewed images are included here:

| View | Synthetic demo capture |
|---|---|
| Orb-only Home, 1440 × 900 | [Desktop](screenshots/voice-first/home-1440.jpg) |
| Orb-only Home, 390 × 844 | [Mobile](screenshots/voice-first/home-390.jpg) |
| Speech failure with retry and text access | [Recovery](screenshots/voice-first/voice-recovery.jpg) |

Existing screenshots are preserved. Audio in automated tests is mocked;
captures are not proof of microphone or speaker performance.

## Limits and remaining work

- Physical MacBook Air M2 microphone, speakers, Safari/Chrome permissions,
  device voices, VoiceOver and platform speech services remain unverified.
- Interruption is explicit: tap/keyboard, then a new listening turn. No continuous
  full-duplex acoustic barge-in or always-listening wake-word service is claimed.
- Browser speech can require internet and send audio to a platform service.
  No audio files are recorded by NEXUS. Core conversation text still follows
  existing local persistence; cloud AI sends scoped context only when enabled.
- Offline speech recognition is not supplied. Broader free-form conversation
  requires the user's configured optional provider. No paid API test was run.
- This remains a trusted local single-user app. Plaintext SQLite and the
  separate browser ledger have their existing limitations. No new encryption,
  secure deletion, external-account access or unrestricted execution is claimed.
- No new blocker remains in the tested synthetic flows. Hardware compatibility
  and the roadmap's advanced capabilities still need separate work.

## Run safely on the MacBook Air M2

Download the new branch ZIP and extract it into a **new folder**. Keep the
existing installation and its `data/` directory in their current location.
In Terminal, type `cd `, drag the new extracted folder into the Terminal window,
then press Return. Run Python rather than trying to execute `app.py` directly:

```bash
python3 app.py --demo
```

Open `http://127.0.0.1:8765` (or the address printed by NEXUS). If an existing
NEXUS process occupies that port, use `python3 app.py --demo --port 8766` and
open `http://127.0.0.1:8766`. Keep Terminal open. Demo uses temporary invented
records and disables cloud AI. It does not open the real installation's SQLite
records. Stop with Control-C.

Tap the orb, review the speech notice, allow browser microphone permission and
try the navigation examples. Test speech interruption by tapping during a reply,
then test Escape, denied permission and text via Command-K. In Settings select
the correct recognition language and a voice actually installed on the Mac.
For OpenAI, use the existing Settings instructions and set the API key privately
in the terminal environment; API billing is separate from ChatGPT. Back up real
data using [DATA_SAFETY.md](DATA_SAFETY.md) before any later reviewed upgrade.

No deployment, automatic merge or modification of the user's Mac installation
was performed. The failed cloud workspace was restarted before implementation;
all results above refer to the recovered working environment.
