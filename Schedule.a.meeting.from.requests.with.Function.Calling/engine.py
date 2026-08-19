import os
import math
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

# Google SDK imports
from google import genai
from google.genai import types

# Local Llama imports
from llama_cpp import Llama
import outlines
from huggingface_hub import hf_hub_download

from schemas import ScheduleCalendarEventFunction

load_dotenv()
logger = logging.getLogger(__name__)


# ==========================================
# 1. BASE PROVIDER INTERFACE
# ==========================================
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_schedule(self, prompt: str) -> ScheduleCalendarEventFunction:
        pass


# ==========================================
# 2. OPENROUTER PROVIDER
# ==========================================
class OpenRouterProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "google/gemini-2.5-flash-lite"):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model_name

    def generate_schedule(self, prompt: str) -> ScheduleCalendarEventFunction:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Calendar Task Engine",
        }

        # Enforce JSON Schema via OpenRouter structured output
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ScheduleCalendarEventFunction",
                    "strict": True,
                    "schema": ScheduleCalendarEventFunction.model_json_schema(),
                },
            },
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            raw_content = result["choices"][0]["message"]["content"]
            return ScheduleCalendarEventFunction.model_validate_json(raw_content)


# ==========================================
# 3. GOOGLE PROVIDER
# ==========================================
class GoogleProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = self._init_client()

    def _init_client(self) -> genai.Client | None:
        if self.api_key:
            return genai.Client(api_key=self.api_key)
        return None

    def generate_schedule(self, prompt: str) -> ScheduleCalendarEventFunction:
        if not self.api_key or not self.client:
            raise ValueError("GEMINI_API_KEY is missing or invalid.")

        # Native schema enforcement via Google GenAI SDK
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ScheduleCalendarEventFunction,
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"  # Restricts deep reasoning tokens to reduce latency
                ),
            ),
        )

        if not response.text:
            raise RuntimeError("Gemini API returned an empty response.")

        return ScheduleCalendarEventFunction.model_validate_json(response.text)


# ==========================================
# 4. LOCAL LLAMA PROVIDER (LAZY LOADED)
# ==========================================
class LocalLlamaProvider(BaseLLMProvider):
    def __init__(
        self,
        repo_id: str = "bartowski/Qwen2.5-0.5B-Instruct-GGUF",
        filename: str = "Qwen2.5-0.5B-Instruct-f16.gguf",
        cache_dir: str = "./models/huggingface",
    ):
        self.repo_id = repo_id
        self.filename = filename
        self.cache_dir = cache_dir
        self._model = None  # Lazy-load holder

    def _initialize_model(self):
        """Loads weights only when first invoked."""

        if self._model is None:
            logger.info(f"Initializing local GGUF model: {self.filename}")
            n_threads = max(3, math.ceil((os.cpu_count() or 4) / 2))

            model_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=self.filename,
                cache_dir=self.cache_dir,
                token=os.environ.get("HF_TOKEN"),
            )

            llm = Llama(model_path=model_path, n_ctx=2048, n_threads=n_threads)
            self._model = outlines.from_llamacpp(llm)

    def generate_schedule(self, prompt: str) -> ScheduleCalendarEventFunction:
        self._initialize_model()

        formatted_prompt = (
            f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        )

        raw_json = self._model(
            formatted_prompt,
            output_type=ScheduleCalendarEventFunction,
            temperature=0.0,
            max_tokens=300,
            stop=["<|im_end|>", "<|endoftext|>"],
        )
        return ScheduleCalendarEventFunction.model_validate_json(raw_json)


# ==========================================
# 4. FALLBACK ENGINE ORCHESTRATOR
# ==========================================
class CalendarFunctionEngine:
    def __init__(self):
        # Define provider priority sequence
        self.providers = [OpenRouterProvider(), GoogleProvider(), LocalLlamaProvider()]

    def _build_prompt(self, request_text: str) -> str:
        now_utc = datetime.now(timezone.utc)
        current_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        current_date_str = now_utc.strftime("%Y-%m-%d (%A)")

        return (
            "You are an AI calendar assistant. Convert scheduling requests into structured JSON arguments.\n"
            f"CURRENT DATETIME REFERENCE (UTC): {current_iso}\n"
            f"CURRENT DATE: {current_date_str}\n\n"
            "CRITICAL RULES:\n"
            "1. Calculate start and end dates relative to CURRENT DATETIME REFERENCE.\n"
            "2. 'tomorrow' means the day immediately following CURRENT DATE.\n"
            "3. Ensure 'start.date_time' and 'end.date_time' are valid ISO 8601 strings (YYYY-MM-DDTHH:MM:SSZ).\n"
            "4. Calculate end time by adding the duration to the start time.\n\n"
            f"User Request: {request_text}"
        )

    def extract_calendar_function(
        self, request_text: str
    ) -> ScheduleCalendarEventFunction:
        prompt = self._build_prompt(request_text)

        for provider in self.providers:
            provider_name = provider.__class__.__name__

            try:
                logger.info(f"Attempting extraction via {provider_name}...")
                return provider.generate_schedule(prompt)
            except Exception as e:
                logger.warning(
                    f"[{provider_name} Failed]: {str(e)}. Attempting fallback..."
                )

        raise RuntimeError("All LLM providers in the fallback chain failed.")


# Singleton accessor
_engine_instance = None


def get_calendar_engine() -> CalendarFunctionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CalendarFunctionEngine()
    return _engine_instance
