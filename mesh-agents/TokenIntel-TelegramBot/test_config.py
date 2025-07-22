import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

import litellm
from dotenv import load_dotenv
from src.model_config import ModelConfig


def test_provider_config():
    """Test the provider configuration logic"""
    load_dotenv()
    provider = os.environ.get("MODEL_PROVIDER")
    model = os.environ.get("MODEL")
    api_key = os.environ.get("API_KEY")
    print("🔍 Testing configuration:")
    print(f"   Provider: {provider}")
    print(f"   Model: {model}")
    print(f"   API Key: {api_key[:10]}..." if api_key else "None")
    print()

    # Test the model configuration
    try:
        config = ModelConfig.from_env()
        print("✅ ModelConfig created successfully")
        print(f"   Provider: {config.provider}")
        print(f"   Model: {config.model}")
        print()
        litellm_model = config.get_litellm_model_name()
        print(f"🔧 LiteLLM model name: {litellm_model}")
        config.setup_environment_keys()
        print(f"🔑 Environment keys set for {config.provider}")
        env_keys = []
        for key in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "XAI_API_KEY",
        ]:
            if os.environ.get(key):
                env_keys.append(key)
        print(f"🌍 Active environment keys: {env_keys}")

        litellm_config = config.get_litellm_config()
        print("⚙️  LiteLLM config:")
        for key, value in litellm_config.items():
            if key == "api_key":
                print(f"   {key}: {str(value)[:10]}...")
            else:
                print(f"   {key}: {value}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_simple_call():
    """Test a simple LiteLLM call"""
    print("\n🧪 Testing simple LiteLLM call...")

    try:
        config = ModelConfig.from_env()
        litellm_config = config.get_litellm_config()
        litellm.set_verbose = True

        print("🔧 Making test call with final config:")
        for key, value in litellm_config.items():
            print(f"   {key}: {value}")
        test_config = litellm_config.copy()
        test_config["max_tokens"] = 20  # Increased from 5 to meet OpenAI minimum

        response = litellm.completion(
            messages=[{"role": "user", "content": "Say 'OK'"}], **test_config
        )

        print(f"✅ Success! Response: {response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"❌ LiteLLM call failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Provider Configuration Debug Test")
    print("=" * 50)

    if test_provider_config():
        test_simple_call()

    print("\n" + "=" * 50)
    print("💡 If you're still getting errors:")
    print("1. Check that MODEL doesn't have provider prefix for Heurist")
    print("2. Verify your Heurist API key is correct")
    print("3. Try a different model name like 'meta-llama/llama-3.1-70b-instruct'")
