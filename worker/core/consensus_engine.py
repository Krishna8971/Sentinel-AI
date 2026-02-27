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
DETECTION_PROMPT = """You are a strict application security auditor. Your job is to find REAL, CONFIRMED authorization vulnerabilities — NOT hypothetical ones.

VULNERABILITY DEFINITIONS:

1. BOLA (Broken Object Level Authorization) — ALL THREE of the following must be true simultaneously:
   a) A user-supplied ID (from path/query/body) is used to look up a SPECIFIC object in the database
   b) The function does NOT verify the authenticated user owns or is authorized to access that specific object
   c) The data returned is user-specific/sensitive (not public data, not aggregated stats)
   NOT BOLA if: the endpoint uses current_user directly, has an admin role check, the query filters BY current_user.id, or middleware handles ownership.

2. IDOR — A user-supplied reference (filename, key, token) directly accesses an internal resource with NO authorization check in the function or its guards. NOT IDOR if: the reference is validated against the authenticated user's session.

3. Privilege Escalation — The function explicitly ASSIGNS or UPGRADES a user's role/is_admin/permissions based on caller input WITHOUT verifying the caller is already an admin.

4. Missing Role Guard — A mutation endpoint (POST/PUT/DELETE) that handles sensitive data has NO auth dependency (Depends), NO middleware guard, AND NO manual auth check in the body. Do NOT flag GET endpoints unless they return clearly sensitive per-user data.

5. Missing Authentication — The function directly reads/writes user data without any form of authentication check anywhere (no Depends, no session check, no token validation).

6. Inconsistent Middleware — Concrete evidence that sibling routes in the same router/file have guards but this one does not, AND the unguarded route accesses sensitive data.

ENDPOINT DATA:
Function Name: {function_name}
Method: {method}
Path: {path}
Auth Guards (Depends): {guards}
Arguments: {arguments}

SOURCE CODE:
{code}

STRICT RULES — you MUST follow these or your answer is wrong:
- If guards list contains ANY dependency (current_user, get_current_user, etc.), do NOT flag Missing Authentication or Missing Role Guard.
- If the DB query filters by current_user.id or current_user itself, do NOT flag BOLA.
- Do NOT flag BOLA just because there is an ID parameter — you need evidence the object isn't ownership-checked.
- Do NOT flag utility/helper functions that don't directly handle HTTP requests as Missing Role Guard.
- If you are not at least 70% confident with clear code evidence, respond with has_vulnerability: false.
- Admin endpoints that intentionally access any user's data are NOT BOLA.

Respond ONLY with this exact JSON (no markdown, no explanation outside JSON):
{{"has_vulnerability": false, "vulnerability_type": "None", "confidence": 0, "reasoning": "One specific sentence citing the exact code evidence for your verdict."}}"""

GEMINI_VALIDATION_PROMPT = """You are a conservative security validation engine. Two AI models analyzed a Python function.
Your job: produce the FINAL verdict. Be skeptical — only confirm if there is CONCRETE code evidence.
If the models found different vulnerability types, or their reasoning is vague, respond with has_vulnerability: false.

FUNCTION CODE:
{code}

MISTRAL FINDING: {mistral_result}
QWEN FINDING: {qwen_result}

VALIDATION RULES:
- If either finding says the function has auth guards or filters by current_user, lean toward clean.
- Only confirm BOLA if you can see a specific object lookup by user-supplied ID with no ownership check.
- Vague reasoning like "no ownership check" without specific code line evidence = not confirmed.

Output ONLY this JSON (no markdown):
{{"has_vulnerability": true/false, "vulnerability_type": "string", "confidence": 0-100, "reasoning": "Final one-sentence verdict citing specific code evidence."}}"""


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

    # Step 3: Final decision — Gemini wins if available, else smart merge
    if gemini_result and gemini_result.get("confidence", 0) > 0:
        return {"status": "gemini_validated", "result": gemini_result}

    # ── Smart merge: Mistral + Qwen weighted agreement ──────────────────────
    # Collect only non-None results
    results = [r for r in [mistral_result, qwen_result] if r]
    if not results:
        return {"status": "all_failed", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "All models unavailable"}}

    # Only one model responded — use it but require high confidence
    if len(results) == 1:
        r = results[0]
        if r.get("has_vulnerability") and r.get("confidence", 0) > 70:
            return {"status": "fallback_mistral", "result": r}
        return {"status": "clean", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "Single model, confidence too low to flag"}}

    m, q = mistral_result, qwen_result
    m_vuln = m.get("has_vulnerability", False) if m else False
    q_vuln = q.get("has_vulnerability", False) if q else False
    m_type = (m.get("vulnerability_type") or "None") if m else "None"
    q_type = (q.get("vulnerability_type") or "None") if q else "None"
    m_conf = m.get("confidence", 0) if m else 0
    q_conf = q.get("confidence", 0) if q else 0

    # Case 1: Both agree there's NO vulnerability → definitive clean
    if not m_vuln and not q_vuln:
        return {"status": "clean", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "Both models agree: no vulnerability"}}

    # Case 2: Both flag a vulnerability of the SAME type → strong consensus, boost confidence
    if m_vuln and q_vuln and m_type == q_type:
        merged_conf = min(100, int((m_conf + q_conf) / 2 * 1.15))  # 15% agreement bonus
        best_reasoning = m.get("reasoning") if m_conf >= q_conf else q.get("reasoning")
        merged = {"has_vulnerability": True, "vulnerability_type": m_type, "confidence": merged_conf, "reasoning": f"[Consensus] {best_reasoning}"}
        return {"status": "consensus", "result": merged}

    # Case 3: Both flag a vulnerability but DIFFERENT types → pick highest confidence, apply penalty
    if m_vuln and q_vuln and m_type != q_type:
        if m_conf >= q_conf:
            best, other_conf = m, q_conf
        else:
            best, other_conf = q, m_conf
        # Penalise disagreement: reduce confidence proportional to the gap
        penalised_conf = int(best.get("confidence", 0) * 0.85)
        if penalised_conf > 60:
            result = dict(best)
            result["confidence"] = penalised_conf
            result["reasoning"] = f"[Disagreement: models differ on type] {best.get('reasoning', '')}"
            return {"status": "judged", "result": result}
        return {"status": "clean", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "Models disagreed on type and penalised confidence too low to flag"}}

    # Case 4: One says vuln, other says clean → only flag if the vuln result has very high confidence
    vuln_result = m if m_vuln else q
    vuln_conf = vuln_result.get("confidence", 0)
    if vuln_conf > 75:
        result = dict(vuln_result)
        result["reasoning"] = f"[Split vote — high confidence] {vuln_result.get('reasoning', '')}"
        return {"status": "judged", "result": result}

    return {"status": "clean", "result": {"has_vulnerability": False, "vulnerability_type": "None", "confidence": 0, "reasoning": "Split vote: single model did not reach confidence threshold (>75) to flag"}}


# Keep old name for backward compatibility
async def analyze_endpoint_parallel(endpoint: Dict[str, Any]) -> Dict[str, Any]:
    return await analyze_endpoint(endpoint)
