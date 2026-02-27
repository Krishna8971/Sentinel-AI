import asyncio
import json
from typing import Dict, Any, List
from core.llm_client import qwen_client, mistral_client

DETECTION_PROMPT = """
You are an expert security engineer analyzing Python FastAPI application authorization configurations.
Given the following endpoint metadata, detect if there are potential BOLA (Broken Object Level Authorization), 
Privilege Escalation, or missing authorization guards.

ENDPOINT DATA:
Function Name: {function_name}
HTTP Method: {method}
Path: {path}
Guards/Depends: {guards}
Arguments: {arguments}

SOURCE CODE:
{code}

Analyze the endpoint. Provide exactly a JSON response in the following schema completely without markdown codeblocks:
{{
  "has_vulnerability": true/false,
  "vulnerability_type": "BOLA" | "Privilege Escalation" | "None",
  "confidence": 0-100,
  "reasoning": "string"
}}
"""

JUDGE_PROMPT = """
You are a senior security architect acting as a consensus judge.
Two AI agents (Qwen and Mistral) analyzed a FastAPI endpoint for authorization vulnerabilities and disagreed.

Model A (Qwen) Analysis:
{qwen_analysis}

Model B (Mistral) Analysis:
{mistral_analysis}

Review the conflicting analysis and provide the final, authoritative judgement in the following JSON format without markdown codeblocks:
{{
  "resolved_vulnerability": true/false,
  "vulnerability_type": "BOLA" | "Privilege Escalation" | "None",
  "confidence": 0-100,
  "reasoning": "string explaining why one model was correct over the other"
}}
"""

async def analyze_endpoint_parallel(endpoint_data: Dict[str, Any]) -> Dict[str, Any]:
    prompt = DETECTION_PROMPT.format(
        function_name=endpoint_data["function_name"],
        method=endpoint_data["method"],
        path=endpoint_data["path"],
        guards=", ".join(endpoint_data["guards"]),
        arguments=", ".join(endpoint_data["arguments"]),
        code=endpoint_data.get("code", "Source code not available")
    )
    
    # Run Qwen and Mistral in parallel
    qwen_task = asyncio.create_task(qwen_client.generate_completion(prompt))
    mistral_task = asyncio.create_task(mistral_client.generate_completion(prompt))
    
    qwen_result = None
    mistral_result = None
    
    try:
        qwen_result = await qwen_task
    except ConnectionError:
        print("Qwen model unavailable. Attempting fallback...")
        
    try:
        mistral_result = await mistral_task
    except ConnectionError:
        print("Mistral model unavailable. Attempting fallback...")
        
    if not qwen_result and not mistral_result:
        return {"status": "error", "message": "CRITICAL: Both Mistral and Qwen AI nodes are utterly unreachable."}
        
    # JSON Parsing
    def _parse(res: str) -> dict:
        if not res: return None
        try:
            return json.loads(res.strip('`').strip('json').strip())
        except json.JSONDecodeError:
            return None
            
    qwen_json = _parse(qwen_result)
    mistral_json = _parse(mistral_result)
    
    # Fallback Logic
    if qwen_json and not mistral_json:
        return {
            "status": "fallback_qwen",
            "result": qwen_json
        }
    elif mistral_json and not qwen_json:
        return {
            "status": "fallback_mistral",
            "result": mistral_json
        }
        
    if not qwen_json and not mistral_json:
         return {"status": "error", "message": "Models responded but both failed to output valid JSON"}

    # Consensus Logic
    if qwen_json.get("has_vulnerability") == mistral_json.get("has_vulnerability") and \
       qwen_json.get("vulnerability_type") == mistral_json.get("vulnerability_type"):
        # They agree
        return {
            "status": "consensus",
            "result": qwen_json
        }
    
    # Needs Judge
    judge_prompt = JUDGE_PROMPT.format(
        qwen_analysis=json.dumps(qwen_json, indent=2),
        mistral_analysis=json.dumps(mistral_json, indent=2)
    )
    
    # Try mistral first as judge, fallback to qwen
    judge_result = None
    try:
        judge_result = await mistral_client.generate_completion(judge_prompt)
    except ConnectionError:
        try:
            judge_result = await qwen_client.generate_completion(judge_prompt)
        except ConnectionError:
            pass
    
    try:
        judge_json = json.loads(judge_result.strip('`').strip('json').strip())
        return {
            "status": "judged",
            "result": judge_json
        }
    except json.JSONDecodeError:
        return {"status": "error", "message": "Judge failed to output valid JSON"}
