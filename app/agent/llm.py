"""Real Claude-backed voice agent (Anthropic Messages API + tool use).

Runs a manual agentic loop so every tool call can be captured for the
demo transcript. Only used when an API key is configured — otherwise
the mock engine in mock.py runs instead and no API calls are made.
"""
import os
import sqlite3

import anthropic

from app.agent import tools
from app.agent.prompt import build_system_prompt

# Default model per Anthropic guidance. Override with KEDS_LLM_MODEL — e.g.
# claude-haiku-4-5 for a cheaper / faster demo.
MODEL = os.environ.get("KEDS_LLM_MODEL", "claude-opus-4-8")
MAX_TOOL_ITERATIONS = 6

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ant profile
    return _client


def run_turn(conn: sqlite3.Connection, caller_phone: str, history: list[dict], user_message: str) -> dict:
    """history is a list of {role, content} text turns from earlier in the call."""
    client = _get_client()
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})

    system = build_system_prompt(caller_phone)
    trace: list[dict] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools.TOOL_SCHEMAS,
            output_config={"effort": "low"},  # terse, fast — fits a phone call
            messages=messages,
        )

        if response.stop_reason == "refusal":
            return {"reply": "Më vjen keq, nuk mund ta ndihmoj me këtë kërkesë.",
                    "trace": trace, "engine": f"claude:{MODEL}"}

        if response.stop_reason != "tool_use":
            reply = "".join(b.text for b in response.content if b.type == "text").strip()
            return {"reply": reply, "trace": trace, "engine": f"claude:{MODEL}"}

        # Execute every requested tool, collect results, loop.
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = tools.run_tool(conn, block.name, block.input)
            trace.append({"tool": block.name, "input": block.input, "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": tools.result_to_content(result),
            })
        messages.append({"role": "user", "content": tool_results})

    return {"reply": "Më falni, po has një vështirësi teknike. Ju lutem provoni sërish.",
            "trace": trace, "engine": f"claude:{MODEL}"}
