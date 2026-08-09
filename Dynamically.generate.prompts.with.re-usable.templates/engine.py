import os
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
import outlines
from huggingface_hub import hf_hub_download, logging
from schemas import SentimentAnalysisOutput


load_dotenv()

logging.set_verbosity_info()

HUGGINGFACE_HUB_TOKEN = os.environ.get("HUGGINGFACE_HUB_TOKEN")

class SentimentEngine:

  def __init__(
      self,
      repo_id: str = "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
      filename: str = "qwen2.5-0.5b-instruct-q4_0.gguf",
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
        tqdm_class=logging.get_progress_bar()
    )

    print(f"Model available at: {model_path}")
      
    self.llm = Llama(
        model_path=model_path,  
        n_ctx=2048,  
        n_threads=n_threads,  
    )

    self.model = outlines.from_llamacpp(self.llm)

    # Reusable dynamic Jinja template using Outlines
    self.template = outlines.Template.from_string("""
    <|im_start|>system
    You are an expert e-commerce sentiment analysis engine. Analyze customer reviews accurately and concisely.
    <|im_end|>
    <|im_start|>user
    Analyze the sentiment of the following Amazon {{ product_category }} {{ content_type }}:

    {% if review_title %}
    Title: {{ review_title }}
    {% endif %}
    Content: {{ text }}

    Provide an overall sentiment, confidence score, summary, and list specific product features evaluated.
    <|im_end|>
    <|im_start|>assistant
    """)

  def analyze_review(
      self,
      text: str,
      product_category: str = "E-Commerce Product",
      content_type: str = "review",
      review_title: str = "",
  ) -> SentimentAnalysisOutput:
    # Dynamically render prompt parameters
    prompt = self.template(
        product_category=product_category,
        content_type=content_type,
        review_title=review_title,
        text=text,
    )

    # Guided structured generation
    raw_json = self.model(
        prompt,
        output_type=SentimentAnalysisOutput,
        temperature=0.1,
        max_tokens=256,
        stop=["<|im_end|>", "<|endoftext|>"],
    )

    return SentimentAnalysisOutput.model_validate_json(raw_json)


_engine = None


def get_sentiment_engine() -> SentimentEngine:
  global _engine
  if _engine is None:
    _engine = SentimentEngine()
  return _engine