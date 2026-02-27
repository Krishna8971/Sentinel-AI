import asyncio
import json
import logging
import re
from typing import Dict, Any
from core.llm_client import mistral_client, qwen_client, gemini_client

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# DETECTION PROMPT — covers all 6 PRD vulnerability types
# ──────────────────────────────────────────────
DETECTION_PROMPT = """You are a senior application security engineer specializing in Python backend authorization vulnerabilities.
Analyze the function below and detect ANY of these vulnerability types:

1. BOLA (Broken Object Level Authorization): An object (DB record, file, resource) is accessed by a user-supplied ID without verifying the requesting user owns or is authorized to access that specific object.
2. IDOR (Insecure Direct Object Reference): A user-supplied parameter directly references an internal object (ID, filename, key) without an authorization check.
3. Privilege Escalation: A function allows changing a user's role, permission level, or administrative status based on caller-supplied input without verifying the caller is an admin.
4. Missing Role Guard: An HTTP endpoint that handles sensitive data or mutations has no authentication/authorization guard (no Depends(), no middleware, no role check in the body).
5. Missing Authentication: A function accesses or modifies user data but does not verify the caller is authenticated at all.
6. Inconsistent Middleware: Related endpoint group where some routes have authorization guards but others in the same file/module do not, creating bypass possibilities.

ENDPOINT/FUNCTION DATA:
Function Name: {function_name}
Method: {method}
Path: {path}
Auth Guards (Depends): {guards}
Arguments: {arguments}

SOURCE CODE:
{code}

RULES:
- Only flag REAL vulnerabilities with clear evidence in the code above.
- A function with both an ID parameter and NO ownership check in the code body = BOLA.
- A function that calls db.query without filtering by current_user = likely BOLA or IDOR.
- If no auth guard AND no manual auth check in body = Missing Auth.
- Do NOT flag vulnerabilities if the code explicitly has an ownership check or role validation.

Respond ONLY with this exact JSON (no markdown, no extra text):
{{"has_vulnerability": true, "vulnerability_type": "BOLA|IDOR|Privilege Escalation|Missing Role Guard|Missing Authentication|Inconsistent Middleware|None", "confidence": 85, "reasoning": "One clear sentence explaining the specific vulnerability found."}}
"""

GEMINI_VALIDATION_PROMPT = """You are a security validation engine. Two AI models analyzed a Python function and produced findings below.
Your job is to produce the FINAL verdict. Be conservative — only confirm if there is solid evidence.

FUNCTION CODE:
{code}

MISTRAL FINDING: {mistral_result}
QWEN FINDING: {qwen_result}

Output ONLY this JSON (no markdown):
{{"has_vulnerability": true/false, "vulnerability_type": "string", "confidence": 0-100, "reasoning": "Final one-sentence verdict."}}
"""


def _parse_json(text: str) -> Dict[str, Any]:
    """Extract JSON from model output, tolerating markdown fences."""
    text = text.strip()
    # strip markdown fences
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```$", "", text)
    # find first JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "Parse error"}


async def _call_model(client, prompt: str, model_name: str) -> Dict[str, Any]:
    try:
        text = await client.generate_completion(prompt)
        result = _parse_json(text)
        logger.info(f"[{model_name}] {result}")
        return result
    except Exception as e:
        logger.warning(f"[{model_name}] unavailable: {e}")
        return None


async def analyze_endpoint(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    prompt = DETECTION_PROMPT.format(
        function_name=endpoint.get("function_name", ""),
        method=endpoint.get("method", "FUNCTION"),
        path=endpoint.get("path", ""),
        guards=endpoint.get("guards", []),
        arguments=endpoint.get("arguments", []),
        code=endpoint.get("code", "")
    )

    # Step 1: Run Mistral and Qwen in parallel
    mistral_task = asyncio.create_task(_call_model(mistral_client, prompt, "Mistral"))
    qwen_task = asyncio.create_task(_call_model(qwen_client, prompt, "Qwen"))
    mistral_result, qwen_result = await asyncio.gather(mistral_task, qwen_task)

    # Step 2: Gemini validation
    gemini_result = None
    if gemini_client.available and (mistral_result or qwen_result):
        val_prompt = GEMINI_VALIDATION_PROMPT.format(
            code=endpoint.get("code", ""),
            mistral_result=json.dumps(mistral_result) if mistral_result else "unavailable",
            qwen_result=json.dumps(qwen_result) if qwen_result else "unavailable"
        )
        try:
            gemini_text = await gemini_client.validate(val_prompt)
            gemini_result = _parse_json(gemini_text)
            logger.info(f"[Gemini] validation: {gemini_result}")
        except Exception as e:
            logger.warning(f"[Gemini] validation error: {e}")

    # Step 3: Final decision — Gemini wins if available, else majority vote
    if gemini_result and gemini_result.get("confidence", 0) > 0:
        return {"status": "gemini_validated", "result": gemini_result}

    # Majority vote between Mistral and Qwen
    results = [r for r in [mistral_result, qwen_result] if r]
    if not results:
        return {"status": "all_failed", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "All models unavailable"}}

    # If either finds a vulnerability with confidence > 60, flag it
    vuln_results = [r for r in results if r.get("has_vulnerability") and r.get("confidence", 0) > 60]
    if vuln_results:
        # Pick highest confidence result
        best = max(vuln_results, key=lambda r: r.get("confidence", 0))
        return {"status": "consensus", "result": best}

    # No vulnerability found
    return {"status": "clean", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "No vulnerability detected"}}


# Keep old name for backward compatibility
async def analyze_endpoint_parallel(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    return await analyze_endpoint(endpoint)
