import os
import logging
from src.connections.openai_connection import OpenAIConnection
from src.connections.anthropic_connection import AnthropicConnection

logger = logging.getLogger("ai_engine")

class AIEngine:
    def __init__(self, config):
        self.config = config
        self.openai = OpenAIConnection(config["openai"])
        self.anthropic = AnthropicConnection(config["anthropic"])

    def generate_response(self, prompt, system_prompt, context_type="default"):
        """Dynamically chooses the best AI model based on context."""
        try:
            if self._should_use_claude(context_type):
                logger.info("⚡ Using Claude for response generation")
                return self.anthropic.generate_text(prompt, system_prompt)
            else:
                logger.info("⚡ Using OpenAI for response generation")
                return self.openai.generate_text(prompt, system_prompt)
        except Exception as e:
            logger.error(f"❌ AI Engine Error: {e}")
            return "Error generating response."

    def _should_use_claude(self, context_type):
        """Determines whether to use Claude based on conversation context."""
        claude_preferred_contexts = ["philosophy", "deep_analysis", "creative_writing"]
        return context_type in claude_preferred_contexts

# Example configuration, update as needed
default_config = {
    "openai": {"model": "gpt-4-turbo"},
    "anthropic": {"model": "claude-3-opus"}
}

# Initialize AI Engine
ai_engine = AIEngine(default_config)
