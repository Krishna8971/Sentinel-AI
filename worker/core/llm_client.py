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
            "temperature": 0.1
            # No max_tokens cap — model decides when done
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info(f"[{self.model_name}] POST {url}")
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(f"[{self.model_name}] OK")
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")


class GeminiClient:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.available = bool(self.api_key and self.api_key != "your_gemini_api_key_here")
        self._model = None
        if self.available:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            # Try flash first, fall back to stable gemini-pro
            for model_name in ("gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-pro"):
                try:
                    self._model = genai.GenerativeModel(model_name)
                    # Quick validate — list models to confirm key works
                    logger.info(f"GeminiClient ready: {model_name}")
                    break
                except Exception as e:
                    logger.warning(f"GeminiClient: {model_name} unavailable: {e}")
            if not self._model:
                self.available = False
                logger.warning("GeminiClient: No Gemini model could be loaded — validation disabled")
        else:
            logger.warning("GeminiClient: No API key — Gemini validation disabled")

    async def validate(self, prompt: str) -> str:
        if not self.available or not self._model:
            return ""
        import asyncio
        import google.generativeai as genai
        fallbacks = ("gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-pro", "gemini-1.0-pro")
        for model_name in fallbacks:
            try:
                model = genai.GenerativeModel(model_name)
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda m=model: m.generate_content(prompt))
                self._model = model  # cache working model
                return response.text
            except Exception as e:
                err = str(e)
                if "404" in err or "not found" in err.lower() or "not supported" in err.lower():
                    logger.warning(f"[Gemini] {model_name} not available, trying next...")
                    continue
                logger.error(f"[Gemini] Error with {model_name}: {e}")
                return ""
        logger.error("[Gemini] All models exhausted — disabling Gemini validation")
        self.available = False
        return ""


mistral_client = LMStudioClient(model_name=MISTRAL_MODEL, base_url=MISTRAL_API_BASE_URL)
qwen_client = LMStudioClient(model_name=QWEN_MODEL, base_url=QWEN_API_BASE_URL)
gemini_client = GeminiClient()
