# antigravity-context-guard

Real-time session token telemetry and strategic `/compact` lifecycle hook plugin for **Google Antigravity (AGY)**.

## Why This Exists

Google Antigravity automatically compacts conversation history (`CHECKPOINT`) once active context (`input_tokens + cache_read_tokens`) reaches roughly **124,000–128,000 tokens**. Because the built-in threshold fires strictly on token count, it often truncates context in the middle of a multi-step debugging loop right after a large tool output.

`context-guard` reads the tail of `transcript.jsonl` before each user turn (`PreInvocation`, `< 5 ms`) and renders a visual progress gauge once your session crosses `85,000` tokens (`68%`), so you can run `/compact` manually at logical task boundaries instead of losing context mid-task.

```markdown
> 🟡 **Context Guard — Warning (`68%`)**  
> `[███████████░░░░░]` **85,400 / ~125,000 tokens** *(~39,600 tokens left before auto-compact)*  
> Good checkpoint to run **`/compact`** once the current task is complete.
```

## Features

- **`PreInvocation` Lifecycle Hook (`hooks.json` -> `scripts/context_monitor.py`)**
  - **Optimal (`< 85,000` tokens / `< 68%`)**: Outputs `{}`. Zero UI noise and zero token overhead.
  - **Warning (`85,000 – 104,999` tokens / `68%–84%`)**: Injects an inline progress bar at the top of the response and instructs the agent to delegate heavy log/file exploration to isolated subagents (`invoke_subagent`).
  - **Critical (`>= 105,000` tokens / `>= 84%`)**: Warns that native `AUTO-COMPACT` will fire within ~20k tokens (or shows exact overshoot) and recommends running `/compact` right after the turn completes.
  - **Anti-Spam State**: Fires only on `invocationNum <= 1` (never inside multi-step tool loops), tracks alerted brackets in `/tmp/agy-context-guard/<conversationId>.json`, and resets automatically after a manual `/compact` or automatic `CHECKPOINT`.
- **On-Demand Telemetry Skill (`/context-guard` -> `scripts/context_status.py`)**
  - Reports active context tokens, cache hit ratio (`cache_read_tokens` vs `input_tokens`), steps since last compaction, and a full breakdown of `MANUAL (/compact)` vs `AUTO-COMPACT` checkpoints in the thread.

## Installation

Clone the repository directly into your global Antigravity plugins directory:

```bash
git clone https://github.com/wojciehm/antigravity-context-guard.git ~/.gemini/config/plugins/context-guard
agy plugin validate ~/.gemini/config/plugins/context-guard
```

Restart Google Antigravity once so the runtime discovers the new plugin bundle. You can toggle it on or off at any time in **Skills & Customizations -> Plugins -> Context Guard**.

## Configuration (Optional Environment Variables)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AGY_COMPACT_CEILING` | `125000` | Empirical token ceiling where Antigravity triggers native `AUTO-COMPACT` |
| `AGY_COMPACT_WARN` | `85000` | Warning tier threshold (~68% of ceiling) |
| `AGY_COMPACT_CRIT` | `105000` | Critical tier threshold (~84% of ceiling) |

## Author

**Wojciech Marusiak** — [wojcieh.net](https://www.wojcieh.net)
