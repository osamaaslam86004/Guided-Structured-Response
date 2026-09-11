"""Token counting utility with optional `tiktoken` support.

Falls back to a characters-based heuristic when `tiktoken` is unavailable.
"""

from math import ceil
from typing import Optional

try:
    import tiktoken

    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """Return an estimated token count for `text`.

    If `tiktoken` is available, uses `cl100k_base` or model-specific encoding.
    Otherwise falls back to `ceil(len(text)/4)`.
    """
    if not text:
        return 0

    if _HAS_TIKTOKEN:
        try:
            # Use model-specific encoding when possible; default to cl100k_base
            encoding_name = "cl100k_base"
            if model:
                # basic mapping for common models; tiktoken will raise if unknown
                if "gpt-4" in model or "gpt" in model:
                    encoding_name = "cl100k_base"
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            pass

    # Fallback heuristic
    return max(1, ceil(len(text) / 4))
