#!/usr/bin/env python3
"""
CLI Diagnostic utility for the Context Guard plugin.
Analyzes token usage, cache efficiency, and compaction history for a given
conversation ID or the most recently active conversations in ~/.gemini/antigravity/brain/,
and generates the visual progress bar banner (`banner_markdown`).
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"
AUTO_COMPACT_CEILING = 125000
WARN_THRESHOLD = 85000
CRIT_THRESHOLD = 105000


def build_progress_bar(pct: float, width: int = 16) -> str:
    clamped = max(0.0, min(100.0, pct))
    filled = max(0, min(width, round((clamped / 100.0) * width)))
    return "█" * filled + "░" * (width - filled)


def build_banner(total: int, ceiling: int) -> str:
    pct = round((total / ceiling) * 100)
    bar = build_progress_bar(pct)
    total_fmt = f"{total:,}".replace(",", " ")
    ceil_fmt = f"{ceiling:,}".replace(",", " ")

    if total >= ceiling:
        over_fmt = f"{total - ceiling:,}".replace(",", " ")
        headroom_str = f"*(przekroczono próg o +{over_fmt} tokenów!)*"
    else:
        rem_fmt = f"{ceiling - total:,}".replace(",", " ")
        headroom_str = f"*(zapas ~{rem_fmt} do auto-compactu)*"

    if total >= CRIT_THRESHOLD:
        icon, label = "🔴", "Poziom Krytyczny"
        footer = "Zalecany natychmiastowy **`/compact`** po zamknięciu bieżącego wątku."
    elif total >= WARN_THRESHOLD:
        icon, label = "🟡", "Ostrzeżenie"
        footer = "Dobry moment na strategiczny **`/compact`** po zamknięciu bieżącego wątku."
    else:
        icon, label = "🟢", "Poziom Optymalny"
        footer = "Bezpieczny zapas okna kontekstowego — kompresja nie jest jeszcze potrzebna."

    return (
        f"> {icon} **Context Guard — {label} (`{pct}%`)**  \n"
        f"> `[{bar}]` **{total_fmt} / ~{ceil_fmt} tokenów** {headroom_str}  \n"
        f"> {footer}"
    )


def analyze_transcript(transcript_path: Path) -> dict:
    conv_id = transcript_path.parents[2].name
    checkpoints = []
    last_ctx = 0
    last_inp = 0
    last_cache = 0
    last_out = 0
    last_step = 0
    steps_since_compact = 0
    total_planner_steps = 0
    last_user_msg = ""

    with transcript_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            t = obj.get("type")
            idx = obj.get("step_index", 0)
            if t == "USER_INPUT":
                lines = (obj.get("content") or "").splitlines()
                last_user_msg = lines[1].strip() if len(lines) > 1 else ""
            elif t == "PLANNER_RESPONSE":
                inp = int(obj.get("input_tokens") or 0)
                cache = int(obj.get("cache_read_tokens") or 0)
                out = int(obj.get("output_tokens") or 0)
                if inp + cache > 0:
                    last_inp = inp
                    last_cache = cache
                    last_out = out
                    last_ctx = inp + cache
                    last_step = idx
                    steps_since_compact += 1
                    total_planner_steps += 1
            elif t == "CHECKPOINT":
                mode = "MANUAL (/compact)" if "/compact" in last_user_msg else "AUTO-COMPACT"
                checkpoints.append(
                    {
                        "step_index": idx,
                        "mode": mode,
                        "ctx_before": last_ctx,
                        "created_at": obj.get("created_at", ""),
                    }
                )
                steps_since_compact = 0
                last_ctx = 21000

    pct = round((last_ctx / AUTO_COMPACT_CEILING) * 100, 1)
    cache_ratio = round((last_cache / last_ctx) * 100, 1) if last_ctx > 0 else 0.0

    return {
        "conversation_id": conv_id,
        "banner_markdown": build_banner(last_ctx, AUTO_COMPACT_CEILING),
        "last_step": last_step,
        "active_tokens": last_ctx,
        "input_tokens": last_inp,
        "cache_read_tokens": last_cache,
        "last_output_tokens": last_out,
        "ceiling_pct": pct,
        "remaining_to_autocompact": max(0, AUTO_COMPACT_CEILING - last_ctx),
        "cache_hit_pct": cache_ratio,
        "steps_since_last_compact": steps_since_compact,
        "total_planner_steps": total_planner_steps,
        "checkpoints": checkpoints,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Antigravity session token usage.")
    parser.add_argument("--conversation-id", "-c", help="Specific conversation UUID to inspect")
    parser.add_argument("--top", "-n", type=int, default=5, help="Number of recent conversations")
    args = parser.parse_args()

    if args.conversation_id:
        tp = BRAIN_DIR / args.conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
        if not tp.is_file():
            print(json.dumps({"error": f"Transcript not found: {tp}"}))
            sys.exit(1)
        print(json.dumps(analyze_transcript(tp), indent=2, ensure_ascii=False))
        return

    transcripts = sorted(
        BRAIN_DIR.glob("*/.system_generated/logs/transcript.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: args.top]

    results = [analyze_transcript(tp) for tp in transcripts]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
