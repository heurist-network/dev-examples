import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
import litellm
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ModelConfig:
    """Configuration class for multi-provider model support"""

    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4000

    @classmethod
    def from_env(cls) -> "ModelConfig":
        """Create ModelConfig from environment variables"""
        provider = os.environ.get("MODEL_PROVIDER", "openai").lower()
        model = os.environ.get("MODEL", "gpt-4o")
        api_key = os.environ.get("API_KEY")
        temperature = float(os.environ.get("TEMPERATURE", "0.1"))
        max_tokens = int(os.environ.get("MAX_TOKENS", "4000"))

        if not api_key:
            raise ValueError("API_KEY is required in environment variables")

        valid_providers = ["openai", "anthropic", "openrouter", "xai", "heurist"]
        if provider not in valid_providers:
            raise ValueError(
                f"MODEL_PROVIDER must be one of: {valid_providers}. Got: {provider}"
            )

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def setup_environment_keys(self):
        """Setup environment variables for LiteLLM based on provider"""
        # Clear any existing API keys to avoid conflicts
        keys_to_clear = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "XAI_API_KEY",
        ]

        for key in keys_to_clear:
            if key in os.environ:
                del os.environ[key]

        # Set the appropriate API key based on provider (following reference pattern)
        if self.provider == "openai":
            os.environ["OPENAI_API_KEY"] = self.api_key

        elif self.provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = self.api_key

        elif self.provider == "openrouter":
            os.environ["OPENROUTER_API_KEY"] = self.api_key

        elif self.provider == "xai":
            os.environ["XAI_API_KEY"] = self.api_key

        elif self.provider == "heurist":
            # For Heurist, set OpenAI key since it's OpenAI-compatible
            os.environ["OPENAI_API_KEY"] = self.api_key

    def get_litellm_model_name(self) -> str:
        """Get the properly formatted model name for LiteLLM based on provider (following reference pattern)"""
        if self.provider == "openai":
            return self.model

        elif self.provider == "anthropic":
            if self.model.startswith("anthropic/"):
                return self.model
            return f"anthropic/{self.model}"

        elif self.provider == "openrouter":
            # For OpenRouter, use openrouter/ prefix to tell LiteLLM to route through OpenRouter
            if self.model.startswith("openrouter/"):
                return self.model
            return f"openrouter/{self.model}"

        elif self.provider == "xai":
            if self.model.startswith("xai/"):
                return self.model
            return f"xai/{self.model}"

        elif self.provider == "heurist":
            # Following the reference pattern from settings.py
            # Heurist is an OpenAI-compatible endpoint, so use openai/ prefix
            if self.model.startswith("openai/"):
                return self.model
            return f"openai/{self.model}"

        return self.model

    def get_litellm_config(self) -> Dict[str, Any]:
        """Get configuration dict for LiteLLM following reference pattern"""
        self.setup_environment_keys()

        config = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Apply provider-specific configuration following reference pattern
        if self.provider == "openai":
            config["model"] = self.model

        elif self.provider == "anthropic":
            config["model"] = (
                f"anthropic/{self.model}"
                if not self.model.startswith("anthropic/")
                else self.model
            )

        elif self.provider == "openrouter":
            # For OpenRouter, we need to use the openrouter/ prefix to tell LiteLLM to route through OpenRouter
            config["model"] = (
                f"openrouter/{self.model}"
                if not self.model.startswith("openrouter/")
                else self.model
            )

        elif self.provider == "xai":
            config["model"] = (
                f"xai/{self.model}" if not self.model.startswith("xai/") else self.model
            )

        elif self.provider == "heurist":
            # Following the exact pattern from reference settings.py
            config["base_url"] = "https://llm-gateway.heurist.xyz/v1"
            config["model"] = (
                f"openai/{self.model}"
                if not self.model.startswith("openai/")
                else self.model
            )

        print(f"🔧 Final LiteLLM config: {config}")
        return config

    def setup_litellm(self):
        """Setup LiteLLM global configuration"""
        self.setup_environment_keys()

        # Configure LiteLLM settings
        litellm.drop_params = True
        litellm.set_verbose = False

        return self.get_litellm_config()

    def __str__(self) -> str:
        return f"ModelConfig(provider={self.provider}, model={self.model})"


class ModelManager:
    """Manager class to handle model operations across providers"""

    def __init__(self):
        self.config = ModelConfig.from_env()
        self.litellm_config = self.config.setup_litellm()
        print(f"🤖 Initialized {self.config}")
        print(f"🔧 Provider: {self.config.provider}")
        print(f"🔧 Raw model from env: {self.config.model}")
        print(
            f"🔧 Final model for LiteLLM: {self.litellm_config.get('model', 'unknown')}"
        )

    async def complete(self, messages: list, **kwargs) -> str:
        """Complete a chat using the configured model"""
        try:
            config = self.config.get_litellm_config().copy()

            # Override config with any passed kwargs (avoid duplicates)
            for key, value in kwargs.items():
                if key in [
                    "temperature",
                    "max_tokens",
                    "top_p",
                    "frequency_penalty",
                    "presence_penalty",
                ]:
                    config[key] = value

            # Use async completion
            response = await litellm.acompletion(messages=messages, **config)

            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ Error in model completion: {e}")
            raise

    def complete_sync(self, messages: list, **kwargs) -> str:
        """Synchronous completion for compatibility"""
        try:
            config = self.config.get_litellm_config().copy()

            # Override config with any passed kwargs (avoid duplicates)
            for key, value in kwargs.items():
                if key in [
                    "temperature",
                    "max_tokens",
                    "top_p",
                    "frequency_penalty",
                    "presence_penalty",
                ]:
                    config[key] = value

            print("🔧 Making sync completion with final config:")
            print(f"   Model: {config.get('model', 'unknown')}")
            print(f"   Provider: {self.config.provider}")
            print(f"   Base URL: {config.get('base_url', 'default')}")
            print(f"   Temperature: {config.get('temperature')}")
            print(f"   Max Tokens: {config.get('max_tokens')}")

            response = litellm.completion(messages=messages, **config)

            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ Error in sync model completion: {e}")
            print(f"🔍 Failed config keys: {list(config.keys())}")
            raise

    def get_model_for_agent(self) -> str:
        """Get the model name to use for Agent initialization"""
        return self.litellm_config.get("model", self.config.model)

    def validate_setup(self) -> bool:
        """Validate that the model configuration is working"""
        try:
            print(f"🔍 Validating {self.config.provider} setup...")

            # Try a simple completion to validate setup
            test_response = self.complete_sync(
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=20,  # Increased to meet minimum requirements
            )

            print(f"✅ Model validation successful: {self.config.provider}")
            print(f"🔗 Model response preview: {test_response[:50]}...")
            return True

        except Exception as e:
            print(f"❌ Model validation failed for {self.config.provider}: {e}")
            return False


# Global model manager instance
try:
    model_manager = ModelManager()
except Exception as e:
    print(f"❌ Failed to initialize ModelManager: {e}")
    print("Please check your .env configuration")
    exit(1)


# Export commonly used functions
def get_model_name() -> str:
    """Get the current model name for agent initialization"""
    return model_manager.get_model_for_agent()


def validate_model_setup() -> bool:
    """Validate the current model setup"""
    return model_manager.validate_setup()


def get_model_config() -> ModelConfig:
    """Get the current model configuration"""
    return model_manager.config


def get_model_manager() -> ModelManager:
    """Get the global model manager instance"""
    return model_manager
