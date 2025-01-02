import uuid
import requests

"""
Demonstrates the use of the Heurist API to interact with an AI model for generating chat completions.

Args:
- api_key (str): The API key required for authenticating with the Heurist API. 
- base_url (str): The endpoint URL for submitting chat completion requests to the Heurist API.

Payload:
- model (str): Specifies the model to be used.
- messages (list): A list of messages to set the conversation context. Each message contains a `role` (e.g., "system", "user") and corresponding `content`.
- temperature (float): Controls randomness in the output. Lower values result in more deterministic responses.
- max_tokens (int): The maximum number of tokens to generate in the response.

Functionality:
- Submits a request to the Heurist API for generating AI-driven chat completions.
- Prints the response status, detailed response data, or error message in case of failure.
"""

def main():
    api_key = "your_user_id#your_api_key"  # For API key, visit: https://dev-api-form.heurist.ai/
    base_url = "https://llm-gateway.heurist.xyz/chat/completions"

    payload = {
        "model": "HEURIST_MODEL_ID",  # For the supported model list, visit: https://github.com/heurist-network/heurist-models/blob/main/models.json
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Describe a beautiful landscape with mountains and a river, avoiding any signs of human presence."}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(base_url, json=payload, headers=headers)

        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print('Request submitted successfully')
            response_data = response.json()
            print(f"Response data: {response_data}")
        else:
            print(f"Error submitting request: {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
