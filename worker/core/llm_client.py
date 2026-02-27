import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Mistral - via lm-proxy sidecar (always reliable, no host networking issues)
MISTRAL_API_BASE_URL = os.getenv("MISTRAL_API_BASE_URL", "http://lm-proxy:8080")
MISTRAL_MODEL = "mistralai/mistral-7b-instruct-v0.3"

# Qwen - optional, gracefully fails if offline
QWEN_API_BASE_URL = os.getenv("QWEN_API_BASE_URL", "http://host.docker.internal:1235")
QWEN_MODEL = "qwen2.5-coder:7b"

# Gemini - cloud validation layer
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


class LMStudioClient:
    def __init__(self, model_name: str, base_url: str):
        self.model_name = model_name
        # Normalize: strip any trailing /v1 or other path suffixes
        self.base_url = base_url.rstrip('/').removesuffix('/v1').removesuffix('/chat')
        logger.info(f"LMStudioClient ready: {self.model_name} at {self.base_url}")

    async def generate_completion(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 120  # Short JSON reply only — speeds up inference 3-4x
        }
        # Mistral gets full 90s; Qwen gets 15s (fail fast if offline)
        timeout = 90.0 if 'mistral' in self.model_name.lower() else 15.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"[{self.model_name}] POST {url}")
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(f"[{self.model_name}] OK — {str(data)[:150]}")
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")


class GeminiClient:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.available = bool(self.api_key and self.api_key != "your_gemini_api_key_here")
        if self.available:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel("gemini-1.5-flash")
            logger.info("GeminiClient ready: gemini-1.5-flash")
        else:
            logger.warning("GeminiClient: No API key configured, Gemini validation disabled")

    async def validate(self, prompt: str) -> str:
        if not self.available:
            return ""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._model.generate_content(prompt)
            )
            return response.text
        except Exception as e:
            logger.error(f"[Gemini] Error: {e}")
            return ""


mistral_client = LMStudioClient(model_name=MISTRAL_MODEL, base_url=MISTRAL_API_BASE_URL)
qwen_client = LMStudioClient(model_name=QWEN_MODEL, base_url=QWEN_API_BASE_URL)
gemini_client = GeminiClient()
