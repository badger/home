# AgentViz badge bridge

This small outgoing-only companion projects AgentViz's actual normalized session
events into bounded Universe 2026 badge snapshots. It is needed because upstream
AgentViz serves raw session files/SSE and normalizes them in browser TypeScript;
it has **no badge/Agent Buddy state endpoint**.

```text
User-selected session file ----\
                               AgentViz parseSession -> metadata filter -> UDP -> badge
AgentViz loopback /api/file ---/
```

The same upstream parsers handle format detection, pairing tool calls/results,
subagents, durations, and token accounting. No upstream files are modified or
vendored. The bridge does not invoke the AgentViz AI Coach or any model/service.
Only the selected local source is read: it does not scan your home directory.

## Setup

Requires **Node.js 22+**, npm, git, and a user-reviewed AgentViz source checkout.
`esbuild` is the bridge's single pinned dependency, also used by AgentViz.
Use the tested revision, not an unpinned latest download:

```sh
git clone https://github.com/jayparikh/agentviz.git /path/to/agentviz
git -C /path/to/agentviz checkout b4c924022745a588497098c241a91458213cf1a3
npm ci --prefix tools/agentviz --ignore-scripts
node -e "console.log(require('node:crypto').randomBytes(16).toString('hex'))"
```

`--source` **executes the parsers from that local checkout** after bundling them in
memory; only use trusted, reviewed source. It checks the upstream Git revision,
but it is not a sandbox and does not validate uncommitted source modifications.
No complete upstream dependency install or AgentViz web build is needed for
direct-file mode.

Create a private host configuration outside the checkout:

```json
{
  "badge": "192.168.1.42",
  "token": "REPLACE_WITH_THE_GENERATED_32_CHARACTER_HEX_TOKEN",
  "port": 9138
}
```

Use the same token in the [badge configuration](../../badge/apps/agentviz/README.md).
`badge` is the badge's IPv4 LAN address; the badge's `host` field is the sending
computer's IPv4 address. Do not commit either real configuration. Prefer file
permissions readable only by your user; no secrets are passed in CLI arguments
or logged. DHCP address changes require updating the corresponding config.
Multiple simultaneous bridges targeting one badge are not supported.

## Use an actual agent session

```sh
node tools/agentviz/bridge.mjs \
  --source /path/to/agentviz \
  --config /path/to/private/host-agentviz.json \
  --session /absolute/path/to/session.jsonl
```

For Copilot CLI, select the intended `~/.copilot/session-state/<id>/events.jsonl`.
Claude Code uses `~/.claude/projects/<project>/<id>.jsonl`; Codex uses rollout
logs under `~/.codex/sessions/`. Existing VS Code/ATIF/prompt-export JSON files
can also be selected. A connected feed of a static export is **not** evidence
that the agent is running. The bridge never changes or appends to source logs.

If already running the upstream **AgentViz CLI with a session file**, reuse its
existing loopback endpoint instead:

```sh
# In the upstream checkout, start the CLI using its own setup instructions:
node bin/agentviz.js /absolute/path/to/session.jsonl

# In this repo, use the actual loopback port printed by that CLI:
node tools/agentviz/bridge.mjs \
  --source /path/to/agentviz \
  --config /path/to/private/host-agentviz.json \
  --url http://127.0.0.1:5173
```

`--url` is a loopback HTTP **origin**, not a path. The bridge polls the existing
`/api/file` snapshot once per second rather than forwarding transcript SSE to the
badge. Bounded snapshot polling naturally handles reconnects and truncation,
without changing upstream server exposure or its loopback request guards.
It follows the **CLI-watched file**, not a different file imported in a browser
tab. Run exactly one source option, `--session` or `--url`.

Stop with Ctrl-C. `--once` sends one snapshot for troubleshooting (not a
continuous live connection). The app reports OFFLINE after five seconds without
an accepted update. Parse/read/HTTP failures send explicit source-error snapshots
instead of keeping old data falsely live; recovery is automatic. A missing source
is retried, so starting before the agent creates its file is supported.

## Bounds, privacy, and protocol

The host accepts sources up to **16 MiB**, reparsing only when a snapshot changes.
Larger logs receive **Session too large**; use the desktop AgentViz for those.
This is intentionally a focused companion, not a production transcript pipeline.
Only complete JSONL records are parsed, and standalone JSON snapshots must be
complete. Existing upstream parse-issue counters cause an error instead of a
success-shaped partial import.

Every second, the bridge sends a complete **version 1 UDP JSON snapshot**, at most
**4096 bytes**. No retry queue or per-event backlog can accumulate on the badge.
One dropped packet is healed by the next snapshot. The badge reads at most two
datagrams per frame and stores at most 24 events plus four top tools.

Fields: `v`, private `token`, random `epoch`, monotonic `seq`, `state`
(`ok`/`waiting`/`error`), allowlisted `message`, sanitized `source` format,
`metrics`, `events`, and `tools`. Metrics are `[events, turns, toolCalls, errors,
durationMs, inputTokens, outputTokens]`, with `-1` for unknown tokens. Each event
is `[originalIndex, timeMs, durationMs, trackIndex, label, agent, error, turnIndex]`;
track indices are reasoning/tool_call/context/output/agent (0-4). The label is a
sanitized tool name or fixed category/lifecycle label, **never event text**.
Agent names are limited to 12 characters, tool labels to 18. Numeric fields are
bounded to signed 31-bit nonnegative integers except the unknown-token sentinel.
Tool entries are `[name, count]`. The four leading tools are counted across the
whole parsed session; the compact Stats screen displays the first two.

Transport is unencrypted, shared-token LAN UDP, **not TLS or a secure
public-network protocol**. Pinning the sender IP, rejecting out-of-order
sequence numbers and recent retired epochs prevents accidental cross-talk and
late datagrams, not a determined LAN attacker. Never expose it to the Internet.
Prompts, transcripts, code, raw data, arguments, results, paths, titles, model
responses, and credentials are explicitly omitted from the outgoing projection.

## Host validation and preview

From this repository root:

```sh
AGENTVIZ_SOURCE=/path/to/agentviz npm test --prefix tools/agentviz
AGENTVIZ_SOURCE=/path/to/agentviz python -m unittest discover -s tests -p 'test_agentviz.py' -v
python .github/scripts/validate_app_readmes.py badge/apps
```

The Python drawing harness uses Pillow (install it in a development virtualenv
if missing). The Node tests use the pinned checkout's existing synthetic fixtures
across all six parsers, subagent lifecycle events, real UDP, and a loopback HTTP
server. Python tests also run the real Node CLI through a real UDP socket into
the production badge receiver, then exercise the production UI logic with
**substitute host drawing and Wi-Fi**, not the 2025 simulator.

```sh
python tools/agentviz/render_preview.py --preview /tmp/agentviz-host-preview.png
python tools/agentviz/render_preview.py --icon badge/apps/agentviz/icon.png
```

The preview is labeled host-generated with synthetic data and a substitute
font. It is not a device screenshot or native-compatibility proof.

Compatibility is pinned to AgentViz
`b4c924022745a588497098c241a91458213cf1a3`: `src/lib/parseSession.ts`,
`sessionTypes.ts`, format parsers, `routes/sessions.js` (`/api/file`), and
`theme.js`/Tracks/Replay UI. Upstream is MIT, Copyright (c) 2026 Jay Parikh;
the preserved license is [LICENSE.agentviz](../../badge/apps/agentviz/LICENSE.agentviz).
