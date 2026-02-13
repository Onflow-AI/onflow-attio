"""
Configuration management for the Discord Lead Bot.
Loads environment variables and provides centralized configuration access.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class Config:
    """Central configuration class for all bot settings."""

    # Discord Configuration
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    # Google AI Studio Configuration
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_MODEL = "gemini-2.5-flash"  # Primary model (2.5 Flash)
    GOOGLE_FALLBACK_MODEL = "gemini-2.5-flash-lite"  # Fallback when quota runs out (2.5 Flash Lite)
    GOOGLE_MAX_TOKENS = 1024

    # Attio CRM Configuration
    ATTIO_API_KEY = os.getenv("ATTIO_API_KEY")
    ATTIO_API_URL = "https://api.attio.com/v2"

    @classmethod
    def validate(cls) -> bool:
        """Validate that all required configuration is present."""
        required_vars = {
            "DISCORD_BOT_TOKEN": cls.DISCORD_BOT_TOKEN,
            "GOOGLE_API_KEY": cls.GOOGLE_API_KEY,
            "ATTIO_API_KEY": cls.ATTIO_API_KEY,
        }

        missing_vars = [var for var, value in required_vars.items() if not value]

        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False

        logger.info("Configuration validation successful")
        return True


# Validate configuration on import
if __name__ != "__main__":
    Config.validate()
