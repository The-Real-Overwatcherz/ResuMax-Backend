"""
ResuMax — AWS Bedrock LLM Client Service
Configures LangChain ChatBedrock models for deep reasoning tasks.
Only initialized if AWS credentials are present.
"""

import structlog
from typing import Optional

from app.config import get_settings

logger = structlog.get_logger(__name__)

_bedrock_deep = None
_bedrock_cheap = None
_bedrock_available = False


def is_bedrock_available() -> bool:
    """Check if Bedrock credentials are configured."""
    global _bedrock_available
    settings = get_settings()
    _bedrock_available = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    return _bedrock_available


def get_bedrock_deep():
    """
    Get the deep reasoning Bedrock model (Claude 3.5 Haiku).
    Returns None if AWS credentials aren't configured.
    """
    global _bedrock_deep

    if not is_bedrock_available():
        logger.debug("bedrock_not_configured", hint="Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return None

    if _bedrock_deep is None:
        try:
            from langchain_aws import ChatBedrockConverse
            settings = get_settings()
            _bedrock_deep = ChatBedrockConverse(
                model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
                region_name=settings.aws_region,
                temperature=0,
                max_tokens=4096,
            )
            logger.info("bedrock_deep_initialized", model="claude-3-5-haiku")
        except Exception as e:
            logger.warning("bedrock_deep_init_failed", error=str(e))
            return None

    return _bedrock_deep


def get_bedrock_cheap():
    """
    Get the cheap Bedrock fallback model (Amazon Nova Micro).
    Returns None if AWS credentials aren't configured.
    """
    global _bedrock_cheap

    if not is_bedrock_available():
        return None

    if _bedrock_cheap is None:
        try:
            from langchain_aws import ChatBedrockConverse
            settings = get_settings()
            _bedrock_cheap = ChatBedrockConverse(
                model_id="amazon.nova-micro-v1:0",
                region_name=settings.aws_region,
                temperature=0,
                max_tokens=2048,
            )
            logger.info("bedrock_cheap_initialized", model="nova-micro")
        except Exception as e:
            logger.warning("bedrock_cheap_init_failed", error=str(e))
            return None

    return _bedrock_cheap
