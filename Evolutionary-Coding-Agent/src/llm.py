import os
import json
from google import genai
from google.genai import types
from src.config import config_instance

class GeminiClient:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Environment variable GEMINI_API_KEY is not set.")
        # Initialize client with API key
        self.client = genai.Client(api_key=api_key)
        self.default_model = config_instance.get("llm.model", "gemini-2.5-flash")
        self.embedding_model = config_instance.get("llm.embedding_model", "gemini-embedding-001")

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = None, json_mode: bool = False, response_schema = None) -> str:
        """
        Generate content using Gemini API.
        """
        import random
        import numpy as np
        seed = config_instance.get("project.seed", 42)
        random.seed(seed)
        np.random.seed(seed)
        
        temp = temperature if temperature is not None else config_instance.get("llm.temperature", 0.1)
        
        config_args = {
            "temperature": temp,
            "seed": seed,
        }
        
        if not json_mode:
            config_args["max_output_tokens"] = config_instance.get("llm.max_output_tokens", 4096)
            
        if system_instruction:
            config_args["system_instruction"] = system_instruction
            
        if json_mode:
            config_args["response_mime_type"] = "application/json"
            if response_schema:
                config_args["response_schema"] = response_schema
                
        config = types.GenerateContentConfig(**config_args)
        
        try:
            response = self.client.models.generate_content(
                model=self.default_model,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            # Fallback or log error
            print(f"Error in LLM Generation: {e}")
            raise e

    def embed(self, text: str) -> list[float]:
        """
        Generate vector embedding for a text.
        """
        if not text.strip():
            # Return zero vector if text is empty
            return [0.0] * 768 # text-embedding-004 defaults to 768 dimensions
        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text
            )
            # Embedding structure in google-genai: response.embeddings[0].values
            return response.embeddings[0].values
        except Exception as e:
            print(f"Error in LLM Embedding: {e}")
            raise e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate vector embeddings for a list of texts.
        """
        if not texts:
            return []
        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=texts
            )
            return [emb.values for emb in response.embeddings]
        except Exception as e:
            print(f"Error in LLM Batch Embedding: {e}")
            raise e

# Create a singleton client instance
llm_client = GeminiClient()
