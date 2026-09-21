import os
import time
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    from pydantic_ai import Agent, ModelSettings
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    _HAS_PYDANTIC_AI = True
except Exception:  # pragma: no cover - defensive; app should not reach here in prod
    _HAS_PYDANTIC_AI = False

OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1"
)
PRIMARY_MODEL = "llama3.2:3b"   # ~45-90s on CPU, one structured call
FALLBACK_MODEL = "qwen3:8b"      # slower, higher quality


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class SummaryOutput(BaseModel):
    """Structured wallet summary — the agent's output_type."""

    consensus_strategy: str = Field(
        description="One-sentence consensus on the trading strategy across all strategy reports"
    )
    key_params: str = Field(
        default="",
        description="Key parameters: entry rule, exit rule, coin, direction, position sizing, leverage",
    )
    disagreements: list[str] = Field(
        default_factory=list,
        description="Points where strategy reports disagree or contradict each other",
    )
    trade_example: str = Field(
        description=(
            "A SHORT, concrete example a copy trader could follow: what to buy "
            "(coin, notional), when, at what price, when to add, and when to sell "
            "(target price / %). Use only what the reports describe; if reports "
            "disagree on the exact numbers, state the range and which report each "
            "figure came from. Keep it to 3-5 sentences and end with a one-line "
            "summary like 'Buy X HYPE at ~$Y, sell the whole stack at +0.84%.'"
        ),
    )
    confidence: Confidence = Field(description="Confidence in the consensus")

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
) -> str:
    def compact(text: str, max_chars: int = 600) -> str:
        # Local 3B models overflow on long reports; ~600 chars x 8 reports
        # fits num_ctx=8192, and includes each report's TL;DR numbers.
        return text.replace("\n", " ").replace("\r", " ")[:max_chars]

    strategy_blocks: list[str] = []
    no_strat_list: list[str] = []
    for label, text in pairs:
        if text.startswith("NO STRATEGY") or "NO STRATEGY" in text[:300]:
            no_strat_list.append(label)
        else:
            strategy_blocks.append(f"=== {label} ===\n{compact(text)}")

    # Cap the number of reports sent to the model (context budget).
    MAX_REPORTS = 8
    if len(strategy_blocks) > MAX_REPORTS:
        keep = strategy_blocks[:MAX_REPORTS]
        dropped = len(strategy_blocks) - MAX_REPORTS
        keep.append(f"=== +{dropped} more reports omitted (same content) ===")
        strategy_blocks = keep

    return (
        f"You are a quant analyst summarizing trading-bot strategy reports for one wallet.\n\n"
        f"Total reports: {total}. Strategy reports: {strategy_count}. "
        f"Reports saying NO STRATEGY: {no_strategy} "
        f"({', '.join(no_strat_list) if no_strategy else 'none'}).\n\n"
        f"Read the {strategy_count} STRATEGY reports below and extract:\n"
        f"1. consensus_strategy: ONE sentence the majority agrees on\n"
        f"2. key_params: ONE plain-text line (no JSON, no brackets, no lists) "
        f"with entry rule, exit rule, coin, direction, sizing, leverage\n"
        f"3. disagreements: list of specific factual contradictions (empty list if none)\n"
        f"4. confidence: 'high' if >=70% of strategy reports agree on core points, "
        f"'medium' if mixed, 'low' if they are thin or contradictory. "
        f"(Note: only {len(strategy_blocks)} of {strategy_count} strategy reports "
        f"are shown above; they are a representative sample.)\n\n"
        f"5. trade_example: a SHORT concrete example a copy trader could follow -- "
        f"what to buy (coin + notional), WHEN, at what price, when to ADD (martingale "
        f"ladder steps), and when to SELL (target price / %). Use only what the "
        f"reports describe. If reports disagree on exact numbers, state the range "
        f"and which report each figure came from. 3-5 sentences, end with a one-line "
        f"summary like 'Buy ~4 HYPE at ~$92, add at -1% steps, sell the whole "
        f"stack at +0.84%.'\n\n"
        f"STRATEGY REPORTS (compact):\n" + "\n\n".join(strategy_blocks)
    )


def _run_agent(model_name: str, prompt: str) -> SummaryOutput:
    """One structured-output call through pydantic-ai (OpenAI-compatible Ollama).

    pydantic-ai enforces the SummaryOutput schema via function-calling / JSON
    mode, so the returned object is already validated -- no manual JSON parsing.
    A single call is ~45-90s on the local 3B model; no tool loop is needed.
    """
    model = OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=OLLAMA_BASE_URL),
    )
    agent = Agent(
        model,
        output_type=SummaryOutput,
        system_prompt=(
            "You are a quant analyst summarizing trading-bot strategy reports "
            "for one wallet. Reply ONLY with the structured fields; no prose "
            "outside the schema. Be concrete and use only what the reports say."
        ),
        model_settings=ModelSettings(temperature=0, timeout=120),
    )
    result = agent.run_sync(prompt)
    return result.output


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
            "trade_example": "",
            "confidence": "low",
            "generated_by": "none",
            "generated_at": "1970-01-01T00:00:00Z",
        }

    prompt = _build_prompt(pairs, total, strategy_count, no_strategy)

    last_err: Optional[str] = None
    for m in [model, FALLBACK_MODEL]:
        try:
            out = _run_agent(m, prompt)
            return {
                "wallet": wallet_dir.name,
                "consensus_strategy": out.consensus_strategy,
                "key_params": out.key_params,
                "disagreements": list(out.disagreements),
                "trade_example": out.trade_example,
                "model_count": total,
                "strategy_report_count": strategy_count,
                "no_strategy_count": no_strategy,
                "confidence": out.confidence.value,
                "generated_by": m,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
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
        "trade_example": "",
        "confidence": "low",
        "generated_by": "error",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


if __name__ == "__main__":
    import json
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
