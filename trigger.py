# trigger.py
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any, Optional

import httpx

# -----------------------------------------------------------------------------
# CRITICAL NETWORK FIX (proxy-proof on your host machine too)
# -----------------------------------------------------------------------------
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)


def arg(key: str, default: str) -> str:
    for i, a in enumerate(sys.argv):
        if a == key and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _extract_text_from_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    out = []
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            out.append(p["text"])
    return "\n".join(out).strip()


def _walk_messages(task: dict) -> list[str]:
    """
    Print agent-facing status messages from history if present.
    """
    msgs: list[str] = []
    hist = task.get("history")
    if isinstance(hist, list):
        for m in hist:
            if not isinstance(m, dict):
                continue
            if m.get("role") != "agent":
                continue
            txt = _extract_text_from_parts(m.get("parts"))
            if txt:
                msgs.append(txt)
    return msgs


def _find_results_artifact(task: dict) -> Optional[dict]:
    artifacts = task.get("artifacts")
    if not isinstance(artifacts, list):
        return None

    for a in artifacts:
        if not isinstance(a, dict):
            continue
        parts = a.get("parts")
        if not isinstance(parts, list):
            continue

        for p in parts:
            if not isinstance(p, dict):
                continue

            # Case A: serialized as {"kind":"data","data": {...}}
            if p.get("kind") == "data" and isinstance(p.get("data"), dict):
                data = p["data"]
                if "results" in data or "summary" in data:
                    return data

            # Case B: python object style {"root":{"kind":"data","data": {...}}}
            root = p.get("root")
            if isinstance(root, dict) and root.get("kind") == "data" and isinstance(root.get("data"), dict):
                data = root["data"]
                if "results" in data or "summary" in data:
                    return data

    return None



async def a2a_jsonrpc_send(
    *,
    base_url: str,
    user_text: str,
    context_id: str,
    timeout_s: float = 1800.0,
) -> dict[str, Any]:
    """
    Sends JSON-RPC "message/send" to Green. Uses blocking=True so this does NOT stream
    and therefore cannot die mid-run with client transport weirdness.
    """
    if "://" not in base_url:
        base_url = "http://" + base_url

    url = base_url.rstrip("/") + "/"

    payload = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": uuid.uuid4().hex,
                "role": "user",
                "contextId": context_id,
                "parts": [{"kind": "text", "text": user_text}],
            },
            "configuration": {"blocking": True},
        },
    }

    timeout = httpx.Timeout(connect=10.0, read=timeout_s, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"A2A error: {data['error']}")
        res = data.get("result")
        if not isinstance(res, dict):
            raise RuntimeError(f"Missing/invalid result: {data}")
        return res


async def main():
    green_url = arg("--green", "http://localhost:8000")
    purple_url = arg("--purple", "http://purple:8001")
    domain = arg("--domain", "blocks")
    index = int(arg("--index", "1"))

    task_payload = {
        "participants": {"planner": purple_url},
        "config": {"domain": domain, "index": index},
    }

    print(f">>> Sending blocking JSON-RPC to Green at {green_url}")
    print(json.dumps(task_payload, indent=2))

    context_id = uuid.uuid4().hex

    try:
        result = await a2a_jsonrpc_send(
            base_url=green_url,
            user_text=json.dumps(task_payload),
            context_id=context_id,
            timeout_s=1800.0,
        )
    except Exception as e:
        print(f"Error during execution: {e}")
        return

    state = (result.get("status") or {}).get("state")
    print(f"\n[task] state={state}")

    # Print any agent messages in history (at end of run)
    msgs = _walk_messages(result)
    if msgs:
        print("\n--- agent messages (history) ---")
        for m in msgs:
            print(m)

    # Extract and save results artifact if present
    artifact_data = _find_results_artifact(result)
    if artifact_data:
        print("\n--- results summary ---")
        summary = artifact_data.get("summary") if isinstance(artifact_data, dict) else None
        if isinstance(summary, dict):
            print(json.dumps(summary, indent=2))
        else:
            print("(no summary field found)")

        os.makedirs("output", exist_ok=True)
        out_path = os.path.join("output", "results.local.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(artifact_data, f, indent=2)
        print(f"\nSaved results artifact to: {out_path}")
    else:
        print("\n(no results artifact found in task response — check green_agent a2a_server artifact emission)")

    # Also save the raw task for debugging
    os.makedirs("output", exist_ok=True)
    raw_path = os.path.join("output", "task.local.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Saved full task response to: {raw_path}")


if __name__ == "__main__":
    asyncio.run(main())
