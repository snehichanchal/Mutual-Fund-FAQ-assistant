import os
import time
from typing import List, Dict, Any, Optional
import groq
from groq import Groq, APITimeoutError, RateLimitError, APIError

from src.config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_RETRY_ATTEMPTS, GROQ_API_KEY

class LLMClient:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        
    def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        for attempt in range(LLM_RETRY_ATTEMPTS):
            try:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                if attempt < LLM_RETRY_ATTEMPTS - 1:
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
                else:
                    raise e
            except APITimeoutError as e:
                if attempt < LLM_RETRY_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise e
            except APIError as e:
                if attempt < LLM_RETRY_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise e
        return None
