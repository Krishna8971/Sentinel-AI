import httpx
import logging
import os

logger = logging.getLogger(__name__)

MISTRAL_API_BASE_URL = os.getenv("MISTRAL_API_BASE_URL", "http://host.docker.internal:1234/v1")
QWEN_API_BASE_URL = os.getenv("QWEN_API_BASE_URL", "http://host.docker.internal:1235/v1")

class LMStudioClient:
    def __init__(self, model_name: str, base_url: str):
        self.model_name = model_name
        self.base_url = base_url
        logger.info(f"Initialized LMStudioClient for {self.model_name} at URL: {self.base_url}")

    async def generate_completion(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful security agent."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1 # Low temp for security analysis determinism
        }
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"[{self.model_name}] Sending HTTP request to {url}")
                response = await client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                logger.info(f"[{self.model_name}] HTTP request successful!")
                # LM Studio uses OpenAI format: {"choices": [{"message": {"content": "..."}}]}
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            logger.error(f"Error connecting to LM Studio node {url}: {str(e)}")
            raise ConnectionError(f"Failed to connect to model {self.model_name}")

# Initialize global clients connecting to external LM Studio endpoints
mistral_client = LMStudioClient(model_name="mistral:7b", base_url=MISTRAL_API_BASE_URL)
qwen_client = LMStudioClient(model_name="qwen2.5-coder:7b", base_url=QWEN_API_BASE_URL)
