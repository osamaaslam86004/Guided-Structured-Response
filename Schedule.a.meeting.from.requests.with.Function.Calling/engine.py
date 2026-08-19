import os
import math
from datetime import datetime, timezone
from llama_cpp import Llama
import outlines
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download, logging
from schemas import ScheduleCalendarEventFunction

load_dotenv()

logging.set_verbosity_info()

HUGGINGFACE_HUB_TOKEN = os.environ.get("HF_TOKEN")


class CalendarFunctionEngine:

    def __init__(
        self,
        repo_id: str = "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        filename: str = "qwen2.5-0.5b-instruct-f16.gguf",
        cache_dir: str = "./models/huggingface",
        n_threads: int = None,
    ):

        if n_threads is None:
            n_threads = max(3, math.ceil(os.cpu_count() / 2))

        print(f"Checking Hugging Face cache for {filename}...")

        model_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=cache_dir,
            token=HUGGINGFACE_HUB_TOKEN,
        )

        print(f"Model available at: {model_path}")

        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=n_threads,
        )

        self.model = outlines.from_llamacpp(self.llm)

    def extract_calendar_function(
        self, request_text: str
    ) -> ScheduleCalendarEventFunction:

        # Dynamically inject current UTC timestamp
        now_utc = datetime.now(timezone.utc)
        current_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        current_date_str = now_utc.strftime("%Y-%m-%d (%A)")

        system_prompt = (
            "You are an AI calendar assistant. Convert user scheduling requests into structured JSON arguments.\n"
            f"CURRENT DATETIME REFERENCE (UTC): {current_iso}\n"
            f"CURRENT DATE: {current_date_str}\n\n"
            "CRITICAL RULES:\n"
            "1. Calculate start and end dates relative to CURRENT DATETIME REFERENCE.\n"
            "2. 'tomorrow' means the day immediately following CURRENT DATE.\n"
            "3. Ensure 'start.date_time' and 'end.date_time' are valid ISO 8601 strings (YYYY-MM-DDTHH:MM:SSZ).\n"
            "4. Calculate end time by adding the duration to the start time."
        )

        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\nConvert this request into a calendar function call:\n{request_text}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        raw_json = self.model(
            prompt,
            output_type=ScheduleCalendarEventFunction,
            temperature=0.0,
            max_tokens=300,
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        return ScheduleCalendarEventFunction.model_validate_json(raw_json)


_engine_instance = None


def get_calendar_engine() -> CalendarFunctionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CalendarFunctionEngine()
    return _engine_instance
