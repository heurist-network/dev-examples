from openai import OpenAI

# Initialize the OpenAI client with the base URL and API key for the custom LLM gateway.
# Replace 'your_user_id#your_api_key' with your actual user_id and API key for the service.
client = OpenAI(base_url="https://llm-gateway.heurist.xyz", api_key="your_user_id#your_api_key")

model_id = "mistralai/mixtral-8x7b-instruct-v0.1"

# Pre-defined messages to set the context for the AI model.
msgs = [
    {"role": "system", "content": "You are a helpful assistant. Your output should be in CAPITAL LETTERS."},
    {"role": "user", "content": "Write 3 short bullet points of the benefits of decentralized AI."},
]

def test_openai_api_stream(messages, temperature=0.75, max_tokens=500):
    """
    Demonstrates the use of the streaming API to get real-time responses from the AI model.

    Args:
    - messages (list): A list of messages to set the context for the AI model.
    - temperature (float, optional): The sampling temperature for controlling the randomness of the output. Default is 0.75.
    - max_tokens (int, optional): The maximum number of tokens to generate. Default is 500.

    This function streams the response from the AI model, printing each part as it's received.
    """
    try:
        stream = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        print("Response from OpenAI Streaming API:")
        for chunk in stream:
            print(chunk.choices[0].delta.content, end="", flush=True)
    except Exception as e:
        print(f"An error occurred during the streaming API call: {e}")

def test_openai_api(messages, temperature=0.75, max_tokens=500):
    """
    Demonstrates the use of the non-streaming API to get a complete response from the AI model.

    Args:
    - messages (list): A list of messages to set the context for the AI model.
    - temperature (float, optional): The sampling temperature for controlling the randomness of the output. Default is 0.75.
    - max_tokens (int, optional): The maximum number of tokens to generate. Default is 500.

    This function waits for the full response from the AI model before printing it out.
    """
    try:
        result = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        print("Response from OpenAI API:")
        print(result.choices[0].message.content)
    except Exception as e:
        print(f"An error occurred during the non-streaming API call: {e}")

if __name__ == "__main__":
    # Example usage of the streaming and non-streaming functions with customizable temperature and max_tokens.
    test_openai_api_stream(msgs, temperature=0.5, max_tokens=200)
    
    # Uncomment the line below to test the non-streaming API with different temperature and max_tokens values.
    # test_openai_api(msgs, temperature=1.0, max_tokens=500)
