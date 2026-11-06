# NEXUS ↔ OpenClaw integration plan — NOT IMPLEMENTED

OpenClaw is optional. NEXUS stores OSIS data locally and does not depend on OpenClaw to boot, chat, run tests, or manage the SQLite database.

## Why wait?

OpenClaw can add channels and tool execution, which also increases the attack surface. Current documentation describes gateway access rules, sandboxing, tool policy, sender allowlists and security audits. These controls must be reviewed for the specific version installed rather than copied blindly from older tutorials.

## Proposed integration phases

**Phase OC-0 (today):** no OpenClaw installation; NEXUS runs on localhost only. Hard-coded deny for any unsupported tool action.

**Phase OC-1 (first future adapter):** independent bridge to translate *authenticated user* read-only request such as `brief`/`tasks` into a NEXUS read-only response. Never expose raw SQLite database or HTTP port publicly. Use a separate authenticated channel, sender allowlist, secrets stored outside repo, bounded message sizes and rate limits.

**Phase OC-2:** allow proposal creation from authorized messages, but require review and confirmation inside the NEXUS UI. A chat thumbs-up or vague phrase is not adequate authorization for any irreversible action.

**Phase OC-3:** if explicit school-approved workflows need it, add minimal external service write adapters that show exactly who receives what, preserve dry-run and fail closed. Use one-time approval, idempotency keys, provider receipts and separate audit.

## Threat controls / minimum design

- Never give bridge shell, unrestricted filesystem, screen recording, browser cookies, or home directory access.
- Keep gateway private, authenticate senders, isolate sessions and deny high-risk tools.
- Treat all chat messages and attached docs as untrusted instructions.
- Use a **read-only first** tool profile; inspect the installed version's configuration and effective tool policy.
- Provide explicit kill switch/disconnect; disable bridge by default.
- No actual student details in bridge chats, logs or external model context without permission.
- Perform `openclaw security audit` (and any supported deeper audit) after configuring.
- Have another person review the authentication boundary before any real OSIS records are exposed.

Official sources:
https://docs.openclaw.ai/gateway/security
https://docs.openclaw.ai/gateway/security/tool-permissions
https://docs.openclaw.ai/gateway/sandboxing
