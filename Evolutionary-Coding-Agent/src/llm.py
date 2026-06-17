import os
import json
import hashlib
import requests
import numpy as np
import random
from src.config import config_instance

class GeminiClient:
    def __init__(self):
        # Read DeepSeek key from env variable or fallback to provided key
        self.api_key = os.environ.get("DEEPSEEK_API_KEY") or "sk-64a423c9e0d6452e978f78dbed99f6f4"
        self.base_url = "https://api.deepseek.com/v1"
        self.default_model = config_instance.get("llm.model", "deepseek-chat")

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = None, json_mode: bool = False, response_schema = None) -> str:
        """
        Generate content using DeepSeek API (OpenAI-compatible).
        """
        seed = config_instance.get("project.seed", 42)
        random.seed(seed)
        np.random.seed(seed)
        
        temp = temperature if temperature is not None else config_instance.get("llm.temperature", 0.1)
        
        # Build messages
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
            
        # Format response_schema if provided to ensure DeepSeek follows it perfectly in JSON Mode
        if json_mode and response_schema:
            if hasattr(response_schema, "model_json_schema"):
                schema_dict = response_schema.model_json_schema()
            elif hasattr(response_schema, "schema"):
                schema_dict = response_schema.schema()
            else:
                schema_dict = response_schema
                
            schema_instruction = (
                f"\n\nCRITICAL: Your response MUST be a JSON object matching this JSON Schema:\n"
                f"{json.dumps(schema_dict, ensure_ascii=False)}\n"
                f"Ensure all required fields are present and correct."
            )
            if messages:
                messages[0]["content"] += schema_instruction
            else:
                messages.append({"role": "system", "content": schema_instruction})
                
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.default_model,
            "messages": messages,
            "temperature": temp,
            "seed": seed
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Error in LLM Generation: {e}")
            if 'response' in locals() and hasattr(response, 'text'):
                print(f"Response details: {response.text}")
            raise e

    def embed(self, text: str) -> list[float]:
        """
        Generate vector embedding for a text locally using feature hashing (768 dimensions).
        """
        dimensions = 768
        if not text or not text.strip():
            return [0.0] * dimensions
            
        words = text.lower().split()
        vector = [0.0] * dimensions
        for word in words:
            h = hashlib.md5(word.encode('utf-8')).hexdigest()
            idx = int(h[:8], 16) % dimensions
            val = 1.0 if int(h[8:16], 16) % 2 == 0 else -1.0
            vector[idx] += val
            
        vec_np = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vec_np)
        if norm > 0:
            vec_np /= norm
            
        return vec_np.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate vector embeddings for a list of texts locally.
        """
        return [self.embed(t) for t in texts]

# Create a singleton client instance
llm_client = GeminiClient()
