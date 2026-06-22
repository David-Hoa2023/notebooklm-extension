import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("loop.storm_adapter")

# Safe imports for knowledge_storm
try:
    from knowledge_storm import STORMWikiRunnerArguments, STORMWikiRunner, STORMWikiLMConfigs
    from knowledge_storm.lm import LitellmModel
    # Try importing DuckDuckGoSearchRM if it exists, otherwise define a dummy/fallback
    try:
        from knowledge_storm.rm import DuckDuckGoSearchRM
    except ImportError:
        # Fallback to a dummy rm if not present
        class DuckDuckGoSearchRM:
            def __call__(self, *args, **kwargs):
                return []

    class SafeLitellmModel(LitellmModel):
        def __call__(self, prompt=None, messages=None, **kwargs):
            # Enforce minimum max_tokens to accommodate reasoning models/tokens
            if "max_tokens" in kwargs:
                kwargs["max_tokens"] = max(kwargs["max_tokens"], 2000)
            else:
                kwargs["max_tokens"] = 2000

            try:
                res = super().__call__(prompt=prompt, messages=messages, **kwargs)
                with open("litellm_calls.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "model": self.model,
                        "prompt": prompt,
                        "messages": messages,
                        "kwargs": {k: v for k, v in kwargs.items() if not k.startswith("api_")},
                        "result": res,
                        "status": "success"
                    }, ensure_ascii=False) + "\n")
                return res
            except Exception as e:
                with open("litellm_calls.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "model": self.model,
                        "prompt": prompt,
                        "messages": messages,
                        "kwargs": {k: v for k, v in kwargs.items() if not k.startswith("api_")},
                        "error": str(e),
                        "status": "error"
                    }, ensure_ascii=False) + "\n")
                raise e

    HAS_STORM = True

    # Monkey patch StormInformationTable to safely handle empty retrieved snippets
    try:
        from knowledge_storm.storm_wiki.modules.storm_dataclass import StormInformationTable
        original_retrieve_information = StormInformationTable.retrieve_information
        
        def safe_retrieve_information(self, queries, search_top_k):
            if not getattr(self, "collected_snippets", None):
                return []
            try:
                return original_retrieve_information(self, queries, search_top_k)
            except ValueError as e:
                if "Expected 2D array" in str(e) or not self.collected_snippets:
                    return []
                raise e
                
        StormInformationTable.retrieve_information = safe_retrieve_information
        logger.info("Successfully monkey-patched StormInformationTable.retrieve_information")
    except Exception as patch_err:
        logger.warning(f"Could not monkey-patch StormInformationTable: {patch_err}")

    # Monkey patch FileIOHelper to use utf-8 for Windows file operations compatibility
    try:
        from knowledge_storm.utils import FileIOHelper
        
        def safe_write_str(s, path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(s)
                
        def safe_load_str(path):
            with open(path, "r", encoding="utf-8") as f:
                return "\n".join(f.readlines())
                
        FileIOHelper.write_str = safe_write_str
        FileIOHelper.load_str = safe_load_str
        logger.info("Successfully monkey-patched FileIOHelper string IO methods to use UTF-8.")
    except Exception as io_patch_err:
        logger.warning(f"Could not monkey-patch FileIOHelper: {io_patch_err}")
except ImportError:
    HAS_STORM = False
    
    class STORMWikiRunnerArguments:
        pass
        
    class STORMWikiRunner:
        pass
        
    class STORMWikiLMConfigs:
        pass
        
    class SafeLitellmModel:
        pass
        
    class DuckDuckGoSearchRM:
        def __call__(self, *args, **kwargs):
            return []

def build_storm_runner(config: Dict[str, Any]) -> Any:
    """
    Builds and configures STORMWikiRunner using OpenRouter/LiteLLM.
    """
    if not HAS_STORM:
        logger.warning("knowledge-storm package not installed. Returning a dummy runner.")
        return DummyRunner(config)

    # Resolve models
    roles = config.get("roles", {})
    executor_model = roles.get("executor_swarm", "moonshotai/kimi-k2.6")
    planner_model = roles.get("planner_verifier", "z-ai/glm-5.2")
    
    # Set up keys and configurations
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_key:
        logger.warning("OPENROUTER_API_KEY not found in environment.")

    # In dspy/LiteLLMModel, we pass configuration to LiteLLMModel
    # Usually: LiteLLMModel(model="openrouter/moonshotai/kimi-k2.6", api_key=openrouter_key, ...)
    lm_configs = STORMWikiLMConfigs()
    
    # Setup models for different roles
    # We prefix openrouter/ to ensure LiteLLM routes it correctly through openrouter
    executor_lm = SafeLitellmModel(
        model=f"openrouter/{executor_model}",
        api_key=openrouter_key,
        max_tokens=2000,
        temperature=0.2
    )
    planner_lm = SafeLitellmModel(
        model=f"openrouter/{planner_model}",
        api_key=openrouter_key,
        max_tokens=2000,
        temperature=0.2
    )
    conv_simulator_model = roles.get("storm_conv_simulator", executor_model)
    conv_simulator_lm = SafeLitellmModel(
        model=f"openrouter/{conv_simulator_model}",
        api_key=openrouter_key,
        max_tokens=2000,
        temperature=0.2
    )
    
    lm_configs.set_question_asker_lm(executor_lm)
    lm_configs.set_conv_simulator_lm(conv_simulator_lm)
    lm_configs.set_outline_gen_lm(planner_lm)
    lm_configs.set_article_gen_lm(planner_lm)
    lm_configs.set_article_polish_lm(planner_lm)

    # Initialize DuckDuckGo RM
    rm = DuckDuckGoSearchRM()

    # Set up engine args
    engine_args = STORMWikiRunnerArguments(
        output_dir=os.path.join("artifacts", "raw", config.get("run_id", "")).replace("\\", "/")
    )
    
    # Configure parameters
    storm_cfg = config.get("storm", {})
    engine_args.max_perspective = storm_cfg.get("max_perspective", 5)
    engine_args.max_conv_turn = storm_cfg.get("max_conv_turn", 3)
    engine_args.search_top_k = storm_cfg.get("search_top_k", 3)

    return STORMWikiRunner(engine_args, lm_configs, rm)

class DummyRunner:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def run(self, topic: str, **kwargs):
        logger.info(f"Dummy runner executing run() with args: {kwargs}")
        pass

    def post_run(self):
        pass

    def summary(self):
        return {"query_count": 0}
