import outlines
import math
import os
from schemas import SupportTicketAnalysis
from llama_cpp import Llama
from typing import Optional


class ProductionEngine:
    def __init__(self, model_path: str = "./models/qwen2.5-0.5b-instruct-q4_0.gguf", n_threads: int = None,):

        # Default to 3 threads or available CPU count
        if n_threads is None:
            n_threads = max(3, math.ceil(os.cpu_count() / 2))

        # 1. Load the GGUF model via llama.cpp on CPU
        llm = Llama(
            model_path=model_path,
            n_ctx=1024,  # Adjust context window if needed
            n_threads=n_threads,  # Adjust based on your available CPU threads
        )

        # 2. Wrap it with Outlines
        self.model = outlines.models.LlamaCpp(llm)


    def analyze(
        self, text: str, custom_prompt: Optional[str] = None) -> SupportTicketAnalysis:
        
        base_instruction = (custom_prompt or "Summarize the support ticket, \
        assess its severity, and list up to 2 DISTINCT actionable items.")

        # Explicit instructions to avoid generic repetition
        prompt = (
            f"<|im_start|>system\n"
            f"You are a ticket triage assistant. Be specific and concise. \
            Do NOT repeat tasks.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Instruction: {base_instruction}\n"
            f"Ticket Content: {text}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        raw_json = self.model(
            prompt,
            output_type=SupportTicketAnalysis,
            temperature=0.2,  # Adds slight variance to prevent generic loops
            max_tokens=256,  # Fast execution limit
            stop=["<|im_end|>", "<|endoftext|>"],
        )

        # Validate and return structured output 
        validated_analysis = SupportTicketAnalysis.model_validate_json(raw_json)

        return validated_analysis


# Singleton Pattern
_engine_instance = None

def get_engine() -> ProductionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProductionEngine()
    return _engine_instance