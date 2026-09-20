import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional

OLLAMA_URL = os.environ.get(
    "OLLAMA_URL", "http://host.docker.internal:11434/api/chat"
)
PRIMARY_MODEL = "llama3.2:3b"   # ~10s, fast
FALLBACK_MODEL = "qwen3:8b"      # ~80s, higher quality

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "consensus_strategy": {
            "type": "string",
            "description": "One-sentence consensus on the trading strategy across all strategy reports",
        },
        "key_params": {
            "type": "string",
            "description": "Key parameters: entry rule, exit rule, coin, direction, position sizing, leverage",
        },
        "disagreements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Points where strategy reports disagree or contradict each other",
        },
        "model_count": {
            "type": "integer",
            "description": "Total number of strategy_report.md files analyzed (including NO STRATEGY)",
        },
        "strategy_report_count": {
            "type": "integer",
            "description": "Number of reports that contain an actual strategy (exclude NO STRATEGY)",
        },
        "no_strategy_count": {
            "type": "integer",
            "description": "Number of reports that say NO STRATEGY",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence in the consensus",
        },
    },
    "required": [
        "consensus_strategy",
        "model_count",
        "strategy_report_count",
        "no_strategy_count",
        "confidence",
    ],
}


def _call_ollama(
    model: str,
    messages: list[dict[str, str]],
    timeout: int = 120,
) -> Optional[str]:
    payload = json.dumps(
        {
            "model": model,
            "format": SUMMARY_SCHEMA,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": 8192, "max_tokens": 2048},
        }
    ).encode()
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception as exc:
        return None
    content = data.get("message", {}).get("content", "")
    if not content.strip().startswith("{"):
        return None
    return content


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    for t in [
        text,
        re.sub(r",\s*([}\]])", r"\1", text),
    ]:
        if t.strip().startswith("{"):
            try:
                return json.loads(t)
            except json.JSONDecodeError:
                continue

def _read_reports(wallet_dir: Path) -> tuple[list[tuple[str, str]], int, int]:
    """Return (label, text) pairs, strategy count, no-strategy count."""
    reports = sorted(wallet_dir.glob("*/strategy_report.md"))
    pairs: list[tuple[str, str]] = []
    no_strategy = 0
    for rp in reports:
        text = rp.read_text(errors="replace").strip()
        is_no = text.startswith("NO STRATEGY") or "NO STRATEGY" in text[:300]
        if is_no:
            no_strategy += 1
        pairs.append((rp.parent.name, text))
    strategy_count = len(pairs) - no_strategy
    return pairs, strategy_count, no_strategy


def _build_prompt(
    pairs: list[tuple[str, str]],
    total: int,
    strategy_count: int,
    no_strategy: int,
) -> list[dict[str, str]]:
    def compact(text: str, max_chars: int = 600) -> str:
        return text.replace("\n", " ").replace("\r", " ")[:max_chars]

    strategy_blocks: list[str] = []
    no_strat_list: list[str] = []
    for label, text in pairs:
        if text.startswith("NO STRATEGY") or "NO STRATEGY" in text[:300]:
            no_strat_list.append(label)
        else:
            strategy_blocks.append(f"=== {label} ===\n{compact(text)}")

    user = (
        f"You are a quant analyst summarizing trading-bot strategy reports for one wallet.\n\n"
        f"Total reports: {total}. Strategy reports: {strategy_count}. "
        f"Reports saying NO STRATEGY: {no_strategy} "
        f"({', '.join(no_strat_list) if no_strategy else 'none'}).\n\n"
        f"Read the {strategy_count} STRATEGY reports below and extract:\n"
        f"1. consensus_strategy: ONE sentence the majority agrees on\n"
        f"2. key_params: entry rule, exit rule, coin, direction, sizing, leverage\n"
        f"3. disagreements: list of specific factual contradictions (empty array if none)\n"
        f"4. confidence: 'high' if >=70% of strategy reports agree on core points, "
        f"'medium' if mixed, 'low' if fewer than {max(1, strategy_count // 3)} strategy reports\n\n"
        f"JSON schema:\n{json.dumps(SUMMARY_SCHEMA, indent=2)}\n\n"
        f"STRATEGY REPORTS (compact):\n" + "\n\n".join(strategy_blocks)
    )
    return [
        {
            "role": "system",
            "content": (
                "Output ONLY a valid JSON object matching the schema. "
                "No markdown, no surrounding text, no explanation. "
                "Be accurate — do not invent facts; use only what is in the reports."
            ),
        },
        {"role": "user", "content": user},
    ]


def generate_summary(
    wallet_dir: Path,
    model: str = PRIMARY_MODEL,
    timeout: int = 120,
) -> dict[str, Any]:
    """
    Generate a structured wallet summary from the strategy reports in `wallet_dir`.

    Reads every `*/strategy_report.md`, filters out pure 'NO STRATEGY' reports,
    sends the rest to Ollama with a JSON schema, and returns the parsed result.
    """
    pairs, strategy_count, no_strategy = _read_reports(wallet_dir)
    total = len(pairs)
    if total == 0:
        return {
            "wallet": wallet_dir.name,
            "error": "no_reports",
            "model_count": 0,
            "strategy_report_count": 0,
            "no_strategy_count": 0,
            "confidence": "low",
            "generated_by": "none",
            "generated_at": "1970-01-01T00:00:00Z",
        }

    messages = _build_prompt(pairs, total, strategy_count, no_strategy)

    last_err: Optional[str] = None
    for m in [model, FALLBACK_MODEL]:
        try:
            raw = _call_ollama(m, messages, timeout=90 if m == PRIMARY_MODEL else 180)
            if raw is None:
                last_err = f"{m} returned no valid response"
                continue
            parsed = _parse_json(raw)
            if parsed is None:
                last_err = f"{m} returned unparseable JSON"
                continue
            missing = [k for k in SUMMARY_SCHEMA["required"] if k not in parsed]
            if missing:
                last_err = f"{m} missing fields: {missing}"
                continue
            parsed["model_count"] = total
            parsed["strategy_report_count"] = strategy_count
            parsed["no_strategy_count"] = no_strategy
            parsed.setdefault("disagreements", [])
            parsed.setdefault("key_params", "")
            parsed["generated_by"] = m
            parsed["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            parsed["wallet"] = wallet_dir.name
            return parsed
        except Exception as exc:
            last_err = f"{m} error: {exc}"
            continue

    return {
        "wallet": wallet_dir.name,
        "error": f"ollama_failed: {last_err}",
        "model_count": total,
        "strategy_report_count": strategy_count,
        "no_strategy_count": no_strategy,
        "consensus_strategy": "",
        "key_params": "",
        "disagreements": [],
        "confidence": "low",
        "generated_by": "error",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


if __name__ == "__main__":
    import sys

    wallet = sys.argv[1] if len(sys.argv) > 1 else "0x0bb81e516c88881c54529e1790470cb5e9f8740d"
    root = Path("/home/paf/Documents/code/misc/hyperliquid-strategy-sweeps")
    wd = root / wallet
    if not wd.is_dir():
        print(f"Wallet dir not found: {wd}", file=sys.stderr)
        sys.exit(1)
    print(f"Generating summary for {wallet} ... ", end="", flush=True)
    t0 = time.time()
    result = generate_summary(wd)
    dt = time.time() - t0
    print(f"Done in {dt:.1f}s (model: {result.get('generated_by', '?')})")
    print(json.dumps(result, indent=2))
