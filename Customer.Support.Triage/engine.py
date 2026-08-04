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
    if n_threads is None:
      n_threads = max(3, math.ceil(os.cpu_count() / 2)) 

    os.makedirs(os.path.dirname(model_path), exist_ok=True) 

    if os.path.exists(model_path): 
      print(f"Loading local model from {model_path}...") 
      llm = Llama(
          model_path=model_path,
          n_ctx=2048,
          n_threads=n_threads,
      ) 
    else:
      print(
          "Model not found at"
          f" {model_path}. Downloading from Hugging Face ({repo_id})..."
      ) 
      llm = Llama.from_pretrained(
          repo_id=repo_id,
          filename=filename,
          local_dir=os.path.dirname(model_path),
          n_ctx=2048,
          n_threads=n_threads,
      ) 

    self.model = outlines.from_llamacpp(llm) 

  def analyze(
      self, text: str, custom_prompt: Optional[str] = None
  ) -> SupportTicketAnalysis:
    # 1. Provide clear rules to guide small models (0.5B)
    rules = (
        "RULES FOR CLASSIFICATION:\n"
        "- Severity: 'low' for feature requests/ui preferences, 'medium' for minor bugs/questions, 'high' for double charges/refunds, 'critical' for system downtime/500 errors.\n"
        "- Teams: 'Billing' for payments/refunds, 'Engineering' or 'DevOps' for server/500 errors/bugs, 'Product' for dark mode/feature requests, 'Support' for general help."
    )

    base_instruction = (
        custom_prompt
        or "Summarize the ticket, assess severity, and assign actionable steps to the correct team."
    )

    prompt = (
        f"<|im_start|>system\n"
        f"You are an expert ticket triage classifier. Follow classification rules strictly.\n"
        f"{rules}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"Instruction: {base_instruction}\n"
        f"Ticket Content: {text}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    raw_json = self.model(
        prompt,
        output_type=SupportTicketAnalysis,
        temperature=0.0,  # GREEDY SAMPLING: forces strict adherence to prompt rules
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