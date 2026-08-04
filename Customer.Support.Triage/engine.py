import math
import os
from typing import Optional
from llama_cpp import Llama
import outlines
from schemas import SupportTicketAnalysis


class ProductionEngine:

  def __init__(
      self,
      model_path: str = "./models/qwen2.5-0.5b-instruct-q8_0.gguf", 
      repo_id: str = "Qwen/Qwen2.5-0.5B-Instruct-GGUF",  
      filename: str = "qwen2.5-0.5b-instruct-q8_0.gguf",  
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

    # System prompt using Few-Shot examples to firmly instruct the 0.5B model
    system_prompt = (
        "You are an automated ticket triage classifier. Follow these mapping rules strictly:\n"
        "1. User Interface and Experience / Feature requests -> team: Product, severity: low\n"
        "2. Server issues / Dashboard crashes -> team: Engineering, severity: critical or high\n"
        "3. Double charges / Refunds / Subscription payments -> team: Billing, severity: high\n"
        "4. General questions / How-to -> team: Support, severity: low or medium"
    )

    # Place custom_prompt as context, prioritizing core triage requirements
    prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"Ticket: {text}\n"
        f"Note: {custom_prompt or 'Perform standard ticket triage'}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    raw_json = self.model(
        prompt,
        output_type=SupportTicketAnalysis,
        temperature=0.0,  # Zero temperature for deterministic enum matching
        max_tokens=256,
        stop=["<|im_end|>", "<|endoftext|>"],  
    )

    return SupportTicketAnalysis.model_validate_json(raw_json)  


_engine_instance = None  


def get_engine() -> ProductionEngine:
  global _engine_instance  
  if _engine_instance is None:  
    _engine_instance = ProductionEngine()  
  return _engine_instance  