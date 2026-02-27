import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional
from core.llm_client import mistral_client, qwen_client, gemini_client

logger = logging.getLogger(__name__)

DETECTION_PROMPT = """Security analysis task. Analyze this Python function for authorization vulnerabilities.

Vulnerability types (pick ONE that fits best, or None):
- BOLA: accesses DB object by user-supplied ID without ownership check
- IDOR: user-supplied param references object without auth check
- Privilege Escalation: changes role/permission from user input without admin check
- Missing Role Guard: HTTP endpoint with no Depends()/role check, exposes sensitive data
- Missing Authentication: no identity verification before data access
- None: code is secure

Function: {function_name} | Method: {method} | Path: {path}
Guards: {guards} | Args: {arguments}

CODE:
{code}

Reply ONLY with this JSON (no markdown, one short sentence for reasoning):
{{"has_vulnerability": true, "vulnerability_type": "BOLA", "confidence": 85, "reasoning": "sentence"}}
"""

GEMINI_VALIDATION_PROMPT = """You are a security validation engine. Analyze findings from two AI models.
Produce a final verdict. Be conservative — only confirm with solid evidence.

CODE:
{code}

MISTRAL: {mistral_result}
QWEN: {qwen_result}

Output ONLY this JSON (no markdown):
{{"has_vulnerability": true, "vulnerability_type": "string", "confidence": 0, "reasoning": "sentence"}}
"""

NULL_RESULT = {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "No issue found"}


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from model output. Returns None on any failure."""
    if not text or not text.strip():
        return None
    try:
        # Strip markdown fences
        text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text)
        # Find the first JSON object in the response
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            obj = json.loads(match.group())
            # Validate required fields are present
            if "has_vulnerability" in obj:
                return obj
    except Exception:
        pass
    return None


async def _call_model_once(client, prompt: str, model_name: str) -> Optional[Dict[str, Any]]:
    """
    Single-shot model call. No retries. Returns None on ANY failure.
    This guarantees we never get stuck in an error loop.
    """
    try:
        text = await client.generate_completion(prompt)
        result = _parse_json(text)
        if result:
            logger.info(f"[{model_name}] ✓ {result.get('vulnerability_type')} conf={result.get('confidence')}")
        else:
            logger.warning(f"[{model_name}] returned unparseable response: {str(text)[:100]}")
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[{model_name}] timed out — skipping")
        return None
    except Exception as e:
        # Log with repr() so empty-string exceptions still show their type
        logger.warning(f"[{model_name}] failed ({repr(e)}) — skipping")
        return None


async def analyze_endpoint(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    code = endpoint.get("code", "")
    if not code.strip():
        return {"status": "skipped", "result": NULL_RESULT}

    prompt = DETECTION_PROMPT.format(
        function_name=endpoint.get("function_name", ""),
        method=endpoint.get("method", "FUNCTION"),
        path=endpoint.get("path", ""),
        guards=endpoint.get("guards", []),
        arguments=endpoint.get("arguments", []),
        code=code
    )

    # Step 1: Mistral and Qwen in parallel — each has exactly ONE attempt, no retries
    mistral_result, qwen_result = await asyncio.gather(
        _call_model_once(mistral_client, prompt, "Mistral"),
        _call_model_once(qwen_client, prompt, "Qwen"),
        return_exceptions=False   # exceptions returned as None via _call_model_once
    )

    # Step 2: Gemini validation (only if at least one model returned a finding)
    gemini_result = None
    any_finding = mistral_result or qwen_result
    if gemini_client.available and any_finding:
        val_prompt = GEMINI_VALIDATION_PROMPT.format(
            code=code,
            mistral_result=json.dumps(mistral_result) if mistral_result else "unavailable",
            qwen_result=json.dumps(qwen_result) if qwen_result else "unavailable"
        )
        try:
            gemini_text = await gemini_client.validate(val_prompt)
            gemini_result = _parse_json(gemini_text)
            if gemini_result:
                logger.info(f"[Gemini] ✓ validated: {gemini_result.get('vulnerability_type')}")
        except Exception as e:
            logger.warning(f"[Gemini] failed ({repr(e)})")

    # Step 3: Final decision — Gemini trumps if confident, else Mistral wins over Qwen
    if gemini_result and isinstance(gemini_result.get("confidence"), (int, float)) and gemini_result["confidence"] > 50:
        return {"status": "gemini_validated", "result": gemini_result}

    # Pick the highest-confidence finding from Mistral/Qwen
    candidates = [r for r in [mistral_result, qwen_result] if r and r.get("has_vulnerability") and r.get("confidence", 0) > 55]
    if candidates:
        best = max(candidates, key=lambda r: r.get("confidence", 0))
        return {"status": "consensus", "result": best}

    # Nothing found / all unavailable
    return {"status": "clean", "result": NULL_RESULT}


# Backward compat alias
async def analyze_endpoint_parallel(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    return await analyze_endpoint(endpoint)
