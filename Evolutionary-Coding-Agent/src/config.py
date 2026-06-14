import os
import random
import yaml
import numpy as np

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.data = {}
        self.load_config()
        self.setup_directories()
        self.setup_seeds()

    def load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f)

    def setup_directories(self):
        # Create default directories
        db_path = self.get("memory.sqlite_db_path", "data/memory/memory.db")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        log_dir = self.get("observability.log_dir", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Temp sandbox directory inside the workspace
        os.makedirs("temp_sandbox", exist_ok=True)

    def setup_seeds(self):
        seed = self.get("project.seed", 42)
        random.seed(seed)
        np.random.seed(seed)
        os.environ["PYTHONHASHSEED"] = str(seed)

    def get(self, key_path: str, default=None):
        keys = key_path.split(".")
        current = self.data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

# Global config instance
config_instance = Config()
