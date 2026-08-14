import os
import math
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
      filename: str = "qwen2.5-0.5b-instruct-q8_0.gguf",
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
        token=HUGGINGFACE_HUB_TOKEN
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

    system_prompt = (
        "You are an AI calendar assistant. Parse user requests into structured Google Calendar event arguments.\n"
        "Ensure dates are formatted in valid ISO 8601 strings (YYYY-MM-DDTHH:MM:SSZ).\n\n"
        "Example:\n"
        "User: Schedule a 30-min meeting with alex@dev.com tomorrow at 10 AM UTC titled Code Review.\n"
        "Function Args:\n"
        "{\n"
        '  "summary": "Code Review",\n'
        '  "description": "Code Review meeting with Alex",\n'
        '  "location": "",\n'
        '  "start": {"date_time": "2026-08-14T10:00:00Z", "time_zone": "UTC"},\n'
        '  "end": {"date_time": "2026-08-14T10:30:00Z", "time_zone": "UTC"},\n'
        '  "attendees": ["alex@dev.com"],\n'
        '  "send_updates": "all"\n'
        "}"
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