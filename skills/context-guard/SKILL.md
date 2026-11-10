---
name: context-guard
description: Inspect session token usage (input + cache tokens), analyze compaction history (manual /compact vs native AUTO-COMPACT), and prepare strategic handover checkpoints before compacting context. Activate when the user asks about token usage, context window status, session length, or preparing for /compact.
---

# Context Guard & Strategic Compact Skill

This skill works alongside the `context-guard` `PreInvocation` lifecycle hook to give visibility into Antigravity's context window usage and prevent unexpected mid-task auto-compactions (`CHECKPOINT` at ~125,000 tokens).

## 1. Checking Live Session Token Usage

Run the bundled diagnostic script passing the current `Conversation ID` (from `<user_information>`):

```bash
python3 ~/.gemini/config/plugins/context-guard/scripts/context_status.py -c <CONVERSATION_ID>
```

Or inspect the 5 most recently active conversations:

```bash
python3 ~/.gemini/config/plugins/context-guard/scripts/context_status.py --top 5
```

### How to Present Results (MANDATORY VISUAL FORMAT)
1. **Always start your response** by outputting the exact `banner_markdown` returned by `context_status.py` verbatim at the very top of your message:
   > 🟡 **Context Guard — Warning (`68%`)**  
   > `[███████████░░░░░]` **85,400 / ~125,000 tokens** *(~39,600 tokens left before auto-compact)*  
   > Good checkpoint to run **`/compact`** once the current task is complete.
2. Below the visual banner, present a concise Markdown table with:
   - **Active Context**: `active_tokens` / `125,000` (`ceiling_pct%`) — broken down into cached tokens (`cache_read_tokens`, `cache_hit_pct%`) and fresh `input_tokens`.
   - **Headroom**: `remaining_to_autocompact` tokens left before Antigravity forces an automatic `CHECKPOINT`.
   - **Compaction History**: Number of manual `/compact` vs automatic `AUTO-COMPACT` checkpoints in the thread.

## 2. Strategic Pre-Compact Handover

When the user asks to prepare for `/compact` (or when context exceeds 85k tokens and a logical milestone is reached):
1. Summarize completed work, modified files (with clickable `file://` links), pending decisions, and exact next commands.
2. Save or update a lightweight handover artifact in `<appDataDir>/brain/<conversation-id>/handover_checkpoint.md` if the task is multi-phase.
3. Recommend that the user execute `/compact` in the chat input before starting the next phase.
