import json
import logging
import os
import re
from typing import List, Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import pandas as pd

from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger("uvicorn.error")

router = APIRouter()

HF_MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731:novita"
HF_BASE_URL = "https://router.huggingface.co/v1"


class ChatMessageItem(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's question or message")
    history: Optional[List[ChatMessageItem]] = Field(
        default_factory=list, description="Recent conversation turns"
    )


class ChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# Budget detection + live optimizer invocation
# ---------------------------------------------------------------------------

# Matches things like: $750k, 750k, $750,000, 750000, $1.5m, 1.5M, $1.2 million
_BUDGET_PATTERN = re.compile(
    r"""\$?\s*
        (?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)
        \s*
        (?P<suffix>k|m|million|thousand)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_BUDGET_CONTEXT_HINTS = re.compile(
    r"budget|allocat|invest|spend|residual eal|optimiz|optimis", re.IGNORECASE
)


def extract_budget_usd(message: str) -> Optional[float]:
    """
    Best-effort extraction of a dollar budget figure from a free-text
    message, e.g. "If I allocate a $750k budget" -> 750000.0.
    Only attempts extraction if the message looks like it's actually
    asking about budget/optimization, to avoid false positives on
    unrelated numeric questions.
    """
    if not _BUDGET_CONTEXT_HINTS.search(message):
        return None

    candidates = []
    for m in _BUDGET_PATTERN.finditer(message):
        num_str = m.group("num")
        suffix = (m.group("suffix") or "").lower()
        if not num_str:
            continue
        try:
            value = float(num_str.replace(",", ""))
        except ValueError:
            continue
        if suffix == "k" or suffix == "thousand":
            value *= 1_000
        elif suffix == "m" or suffix == "million":
            value *= 1_000_000
        # Ignore tiny numbers (likely not a budget, e.g. "control 2")
        if value >= 1_000:
            candidates.append(value)

    if not candidates:
        return None
    # Assume the largest plausible number in the message is the budget
    return max(candidates)


def run_live_optimizer(load_parquet_func, budget_usd: float) -> Optional[dict]:
    """
    Runs the actual Knapsack ILP optimizer (same one /controls/optimize
    uses) for the given budget, and returns a compact JSON-safe summary.
    Returns None if it can't be run (e.g. missing data/module).
    """
    try:
        from risk_engine.investment_optimizer import optimize_investments
    except Exception as e:
        logger.warning(f"Could not import investment optimizer for chat: {e}")
        return None

    try:
        scenarios_df = load_parquet_func("control_scenario_results.parquet")
        result = optimize_investments(
            scenarios_df, budget_usd=budget_usd, one_control_per_asset=True
        )
        selected = result["selected"].to_dict(orient="records")
        return {
            "budget_usd": budget_usd,
            "total_cost_usd": result["total_cost_usd"],
            "total_risk_reduction_usd": result["total_risk_reduction_usd"],
            "budget_utilization_pct": result["budget_utilization_pct"],
            "n_actions_selected": result["n_actions_selected"],
            "residual_eal_usd": result["residual_eal_usd"],
            "greedy_comparison": result["greedy_comparison"],
            "selected_actions": selected,
        }
    except Exception as e:
        logger.warning(f"Could not run live optimizer for chat (budget={budget_usd}): {e}")
        return None


def get_risk_context_json(load_parquet_func, live_optimizer_result: Optional[dict] = None) -> str:
    """
    Extracts high-level and top-risk data into a compact JSON context string:
    - org_risk_summary.parquet
    - business_unit_risk_summary.parquet
    - Top 15 assets by EAL_usd from asset_risk_summary.parquet
    - Top 10 controls by overall_ROSI from control_scenario_results.parquet
    - (optional) live_optimizer_result: real ILP output for a budget
      the user asked about in THIS message
    """
    context = {}

    try:
        org_df = load_parquet_func("org_risk_summary.parquet")
        context["organization_risk_summary"] = org_df.to_dict(orient="records")
    except Exception as e:
        logger.warning(f"Could not load org_risk_summary for chat context: {e}")
        context["organization_risk_summary"] = []

    try:
        bu_df = load_parquet_func("business_unit_risk_summary.parquet")
        context["business_units_risk"] = bu_df.to_dict(orient="records")
    except Exception as e:
        logger.warning(f"Could not load business_unit_risk_summary for chat context: {e}")
        context["business_units_risk"] = []

    try:
        asset_df = load_parquet_func("asset_risk_summary.parquet")
        cols_to_keep = [
            col
            for col in [
                "asset_id",
                "business_unit",
                "criticality",
                "EAL_usd",
                "VaR95_usd",
                "VaR99_usd",
                "priority_score",
            ]
            if col in asset_df.columns
        ]
        top_assets = (
            asset_df.sort_values(by="EAL_usd", ascending=False)
            .head(15)[cols_to_keep]
            .to_dict(orient="records")
        )
        context["top_15_risk_assets"] = top_assets
    except Exception as e:
        logger.warning(f"Could not load asset_risk_summary for chat context: {e}")
        context["top_15_risk_assets"] = []

    try:
        ctrl_df = load_parquet_func("control_scenario_results.parquet")
        grouped = (
            ctrl_df.groupby(["control_id", "control_name"])
            .agg(
                total_cost_usd=("cost_usd", "sum"),
                total_risk_reduction_usd=("Risk_Reduction_usd", "sum"),
                applicable_assets=("asset_id", "count"),
            )
            .reset_index()
        )
        grouped["overall_ROSI"] = (
            grouped["total_risk_reduction_usd"] / grouped["total_cost_usd"]
        )
        top_controls = (
            grouped.sort_values(by="overall_ROSI", ascending=False)
            .head(10)
            .to_dict(orient="records")
        )
        context["top_10_controls_by_ROSI"] = top_controls
    except Exception as e:
        logger.warning(f"Could not load control_scenario_results for chat context: {e}")
        context["top_10_controls_by_ROSI"] = []

    if live_optimizer_result is not None:
        context["live_optimizer_result_for_this_query"] = live_optimizer_result

    return json.dumps(context, indent=2, default=str)


def format_chat_history(history: List[ChatMessageItem]) -> str:
    if not history:
        return "None"
    formatted = []
    for item in history:
        role_label = "User" if item.role == "user" else "Assistant"
        formatted.append(f"{role_label}: {item.content}")
    return "\n".join(formatted)


def get_hf_client():
    global OpenAI
    if OpenAI is None:
        try:
            from openai import OpenAI
        except ImportError:
            raise HTTPException(
                status_code=502,
                detail="openai package is not installed in the active Python environment. Please ensure you are running with `venv` activated and restart the backend server.",
            )
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        raise HTTPException(
            status_code=502,
            detail="HF_TOKEN environment variable is not configured on the backend. Please set it in backend/.env.",
        )
    return OpenAI(base_url=HF_BASE_URL, api_key=hf_token)


@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(req: ChatRequest):
    client = get_hf_client()

    # Late import of load_parquet to avoid circular imports
    from api.main import load_parquet

    # If the user's message looks like a budget/optimization question,
    # actually run the real ILP optimizer instead of letting the LLM guess.
    live_optimizer_result = None
    budget_usd = extract_budget_usd(req.message)
    if budget_usd is not None:
        live_optimizer_result = run_live_optimizer(load_parquet, budget_usd)

    try:
        context_json = get_risk_context_json(load_parquet, live_optimizer_result)
    except Exception as e:
        logger.exception("Error loading risk context for chat")
        context_json = "{}"

    history_str = format_chat_history(req.history)

    system_prompt = f"""You are a cyber risk analyst assistant for this organization's cyber risk dashboard.
Answer questions using ONLY the data below (this is the organization's live, computed risk data — treat it as ground truth and do not use outside/general knowledge to override it). If the data doesn't contain the answer, say so honestly rather than guessing. Give concise, board-appropriate answers in plain English, citing specific $ figures and asset/business-unit names from the data when relevant.

IMPORTANT — budget & investment optimization questions:
Do NOT attempt to compute budget-constrained optimization results yourself (e.g. "if I allocate $X, what's the residual EAL", "what's the best use of a $X budget"). This requires the Knapsack ILP solver, which you cannot run or replicate through reasoning.
- If a "live_optimizer_result_for_this_query" object is present in the data below, that IS the real ILP solver's output for the budget the user asked about — use it directly and cite its numbers (total_cost_usd, total_risk_reduction_usd, residual_eal_usd, n_actions_selected, selected_actions, greedy_comparison). Do not recompute or second-guess it.
- If no "live_optimizer_result_for_this_query" object is present but the user is asking a budget/optimization question, tell them you don't have a live optimizer result for that figure and suggest they use the Investment Optimizer panel on the dashboard, or ask them to confirm the exact budget so it can be computed.
- The "top_10_controls_by_ROSI" data below is a portfolio-wide aggregate per control (summed across all assets it could apply to) — it is NOT a per-asset cost, and must never be presented as "the cost to deploy this control" without clarifying it's the total across all applicable assets.

CURRENT RISK DATA (JSON):
{context_json}

CONVERSATION HISTORY:
{history_str}
"""

    try:
        completion = client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.message},
            ],
        )
        reply_text = (
            completion.choices[0].message.content
            if completion and completion.choices
            else "I am unable to generate a response at this time."
        )
        return ChatResponse(reply=reply_text)
    except Exception as e:
        logger.exception(f"Hugging Face router API invocation failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"AI Chatbot service error from Hugging Face router: {str(e)}",
        )