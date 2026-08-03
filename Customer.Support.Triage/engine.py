import math
import os
from typing import Optional
from llama_cpp import Llama
import outlines
from schemas import SupportTicketAnalysis


class ProductionEngine:

  def __init__(
      self,
      model_path: str = "./models/qwen2.5-0.5b-instruct-q4_0.gguf",
      repo_id: str = "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
      filename: str = "qwen2.5-0.5b-instruct-q4_0.gguf",
      n_threads: int = None,
  ):
        # Default to 3 threads or available CPU count
        if n_threads is None:
            n_threads = max(3, math.ceil(os.cpu_count() / 2))

        # 1. Ensure target directory exists
        os.makedirs(os.path.dirname(model_path), exist_ok=True)

        # 2. Check if model exists locally, otherwise auto-download from Hugging Face
        if os.path.exists(model_path):
            print(f"Loading local model from {model_path}...")
            llm = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=n_threads,
            )
        else:
            print(f"Model not found at {model_path}. Downloading from Hugging Face ({repo_id})...")
            llm = Llama.from_pretrained(
                repo_id=repo_id,
                filename=filename,
                local_dir=os.path.dirname(model_path),
                n_ctx=2048,
                n_threads=n_threads,
            )

        # 3. Wrap with Outlines
        self.model = outlines.from_llamacpp(llm)

    def analyze(self, text: str, custom_prompt: Optional[str] = None) -> SupportTicketAnalysis:
        base_instruction = (
            custom_prompt
            or "Summarize the support ticket, assess its severity, and list up to 2 distinct \
            actionable items."
        )

        prompt = (
            f"<|im_start|>system\n"
            f"You are a ticket triage assistant. Be concise.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Instruction: {base_instruction}\n"
            f"Ticket: {text}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        raw_json = self.model(
            prompt,
            output_type=SupportTicketAnalysis,
            temperature=0.1,
            max_tokens=300,
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        return SupportTicketAnalysis.model_validate_json(raw_json)


_engine_instance = None

def get_engine() -> ProductionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProductionEngine()
    return _engine_instance