#!/usr/bin/env python3
"""
Antigravity PreInvocation Hook: Context Guard (Strategic Compact Monitor)
Reads the active conversation's transcript.jsonl tail, computes total active context
(input_tokens + cache_read_tokens), and injects an ephemeral instruction so the agent
renders the visual Context Guard progress bar at the top of its reply when approaching
or exceeding Antigravity's ~125k auto-compact threshold.

NOTE: Do not use `systemMessage.metadata` here — Antigravity's Go `utils.scrubMessage`
(`proto_utils.go:34`) panics (`cannot convert string to message`) when iterating over
protobuf `map<string, string>` fields in hook outputs. Using `ephemeralMessage` avoids
the protobuf map reflection bug completely and leaves zero permanent tokens in history.
"""

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

AUTO_COMPACT_CEILING = int(os.environ.get("AGY_COMPACT_CEILING", "125000"))
WARN_THRESHOLD = int(os.environ.get("AGY_COMPACT_WARN", "85000"))    # ~68%
CRIT_THRESHOLD = int(os.environ.get("AGY_COMPACT_CRIT", "105000"))   # ~84%

STATE_DIR = Path("/tmp/agy-context-guard")


def resolve_transcript_path(payload: dict) -> Path | None:
    tp = payload.get("transcriptPath")
    if tp:
        p = Path(tp).expanduser()
        if p.is_file():
            return p

    conv_id = payload.get("conversationId")
    if conv_id:
        fallback = (
            Path.home()
            / ".gemini"
            / "antigravity"
            / "brain"
            / conv_id
            / ".system_generated"
            / "logs"
            / "transcript.jsonl"
        )
        if fallback.is_file():
            return fallback
    return None


def read_latest_context_metrics(transcript_path: Path) -> dict | None:
    """Read the last ~256 KB of transcript.jsonl and walk backwards."""
    try:
        size = transcript_path.stat().st_size
        read_bytes = min(size, 262144)
        with transcript_path.open("rb") as f:
            if size > read_bytes:
                f.seek(size - read_bytes)
            raw = f.read().decode("utf-8", errors="ignore")

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if size > read_bytes and lines:
            lines = lines[1:]

        for line in reversed(lines):
            try:
                obj = json.loads(line)
            except Exception:
                continue

            step_type = obj.get("type")
            if step_type == "CHECKPOINT":
                return {
                    "compacted": True,
                    "step_index": obj.get("step_index", 0),
                    "total_tokens": 21000,
                }
            if step_type == "PLANNER_RESPONSE":
                inp = int(obj.get("input_tokens") or 0)
                cache = int(obj.get("cache_read_tokens") or 0)
                out = int(obj.get("output_tokens") or 0)
                total = inp + cache
                if total > 0:
                    return {
                        "compacted": False,
                        "step_index": obj.get("step_index", 0),
                        "input_tokens": inp,
                        "cache_read_tokens": cache,
                        "output_tokens": out,
                        "total_tokens": total,
                    }
    except Exception:
        return None
    return None


def load_state(conv_id: str) -> dict:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        sf = STATE_DIR / f"{conv_id}.json"
        if sf.is_file():
            return json.loads(sf.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_level": "none", "last_tokens": 0, "last_step": 0}


def save_state(conv_id: str, state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        sf = STATE_DIR / f"{conv_id}.json"
        sf.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def build_progress_bar(pct: int, width: int = 16) -> str:
    clamped = max(0, min(100, pct))
    filled = max(0, min(width, round((clamped / 100) * width)))
    return "█" * filled + "░" * (width - filled)


def format_banner(total: int, ceiling: int, level: str) -> str:
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

    if level == "crit":
        return (
            f"> 🔴 **Context Guard — Poziom Krytyczny (`{pct}%`)**  \n"
            f"> `[{bar}]` **{total_fmt} / ~{ceil_fmt} tokenów** {headroom_str}  \n"
            f"> Dobry moment na strategiczny **`/compact`** po zamknięciu bieżącego wątku."
        )
    return (
        f"> 🟡 **Context Guard — Ostrzeżenie (`{pct}%`)**  \n"
        f"> `[{bar}]` **{total_fmt} / ~{ceil_fmt} tokenów** {headroom_str}  \n"
        f"> Dobry moment na strategiczny **`/compact`** po zamknięciu bieżącego wątku."
    )


def main() -> None:
    try:
        raw_in = sys.stdin.read().strip()
        payload = json.loads(raw_in) if raw_in else {}
    except Exception:
        print("{}")
        return

    inv_num = int(payload.get("invocationNum") or 1)
    if inv_num > 1:
        print("{}")
        return

    conv_id = payload.get("conversationId") or "default"
    transcript_path = resolve_transcript_path(payload)
    if not transcript_path:
        print("{}")
        return

    metrics = read_latest_context_metrics(transcript_path)
    if not metrics or metrics.get("compacted"):
        save_state(conv_id, {"last_level": "none", "last_tokens": 0, "last_step": 0})
        print("{}")
        return

    total = metrics["total_tokens"]
    step_idx = metrics["step_index"]
    state = load_state(conv_id)

    if total < WARN_THRESHOLD:
        if state.get("last_level") != "none":
            save_state(conv_id, {"last_level": "none", "last_tokens": total, "last_step": step_idx})
        print("{}")
        return

    should_notify = False
    level = "warn"

    if total >= CRIT_THRESHOLD:
        level = "crit"
        if (
            state.get("last_level") != "crit"
            or (total - int(state.get("last_tokens", 0))) >= 8000
        ):
            should_notify = True
    else:
        level = "warn"
        if (
            state.get("last_level") == "none"
            or (total - int(state.get("last_tokens", 0))) >= 10000
        ):
            should_notify = True

    if not should_notify:
        print("{}")
        return

    save_state(
        conv_id,
        {"last_level": level, "last_tokens": total, "last_step": step_idx},
    )

    banner = format_banner(total, AUTO_COMPACT_CEILING, level)
    pct = round((total / AUTO_COMPACT_CEILING) * 100)

    ephemeral = (
        f"[Context Guard Hook — {level.upper()}: {total}/{AUTO_COMPACT_CEILING} tokens ({pct}%)].\n"
        "MANDATORY UI REQUIREMENT: You MUST include the following exact Markdown blockquote at the VERY TOP "
        "of your final response to the user (before any other text), verbatim:\n\n"
        f"{banner}\n\n"
        "Also keep tool calls concise and delegate heavy file/log reading to invoke_subagent."
    )

    out = {
        "injectSteps": [
            {
                "ephemeralMessage": ephemeral
            }
        ]
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
