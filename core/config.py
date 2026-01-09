import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(verbose=True)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "toor")
    DB_NAME: str = os.getenv("DB_NAME", "test_db")

    # HuggingFace Model
    HF_API_URL = os.getenv("HF_API_URL", "https://router.huggingface.co/v1")
    HF_MODEL: str = os.getenv("HF_MODEL_NAME", "defog/sqlcoder-7b-2")
    HF_API_TOKEN: str = os.getenv("HF_TOKEN")

    # MCP Server Configuration
    MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "localhost")
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8000"))

    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "localhost")
    API_PORT: int = int(os.getenv("API_PORT", "8001"))

    # Application Paths
    BASE_DIR: Path = Path(__file__).parent.parent

    def validate(self):
        """Validate configuration"""
        required_vars = {
            "DB_HOST": self.DB_HOST,
            "DB_USER": self.DB_USER,
            "DB_NAME": self.DB_NAME,
            "HF_MODEL": self.HF_MODEL,
            "HF_API_URL": self.HF_API_URL
        }

        missing = [var for var, value in required_vars.items() if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


# Create and validate config
config = Config()

try:
    config.validate()
    logger.info("Configuration validated")
except ValueError as e:
    logger.info("Configuration error: {e}")