# antigravity-context-guard

Real-time session token telemetry and strategic `/compact` lifecycle hook plugin for **Google Antigravity (AGY)**.

## Why This Exists

Google Antigravity automatically compacts conversation history (`CHECKPOINT`) once active context (`input_tokens + cache_read_tokens`) reaches roughly **250,000–256,000 tokens** on Gemini 4 models (or **124,000–128,000 tokens** on smaller/Flash models). Because the built-in threshold fires strictly on token count, it can truncate context in the middle of a multi-step debugging loop right after a large tool output.

At the same time, running `/compact` too early hurts accuracy because compaction is lossy and discards cached file/log reads. `context-guard` reads the tail of `transcript.jsonl` before each user turn (`PreInvocation`, `< 5 ms`) and stays completely silent until your session crosses `175,000` tokens (`68%` of the 256k ceiling), advising you to keep going if you are on the same task and only run `/compact` when switching topics or approaching `225,000` tokens (`88%`).

```markdown
> 🟡 **Context Guard — Warning (`68%`)**  
> `[███████████░░░░░]` **175,400 / ~256,000 tokens** *(~80,600 tokens left before ~256k auto-compact)*  
> Keep going if on the same task; run **`/compact`** only when switching to a new topic.
```

## Features

- **`PreInvocation` Lifecycle Hook (`hooks.json` -> `scripts/context_monitor.py`)**
  - **Optimal (`< 175,000` tokens / `< 68%`)**: Outputs `{}`. Zero UI noise and zero token overhead.
  - **Warning (`175,000 – 224,999` tokens / `68%–88%`)**: Injects an inline progress bar once (and every +25k tokens) reminding you to compact only when switching topics, while nudging the agent to delegate heavy log exploration to isolated subagents (`invoke_subagent`).
  - **Critical (`>= 225,000` tokens / `>= 88%`)**: Warns that native `AUTO-COMPACT` (`~256k`) is ~30k tokens away and recommends running `/compact` after the current task finishes.
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
| `AGY_COMPACT_CEILING` | `256000` | Empirical token ceiling where Antigravity triggers native `AUTO-COMPACT` on Gemini 4 |
| `AGY_COMPACT_WARN` | `175000` | Warning tier threshold (~68% of ceiling) |
| `AGY_COMPACT_CRIT` | `225000` | Critical tier threshold (~88% of ceiling) |

## Author

**Wojciech Marusiak** — [wojcieh.net](https://www.wojcieh.net)
