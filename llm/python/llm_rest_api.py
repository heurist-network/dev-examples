import uuid
import requests

# Main function to interact with the API
def main():
    api_key = "your_user_id#your_api_key"  # Replace with a secure method to load the API key
    base_url = "https://llm-gateway.heurist.xyz/chat/completions"

    # Define the payload for the chat completions API
    payload = {
        "model": "YOUR_MODEL_ID", # Replace with desired model
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
        # Submit the request using an HTTP POST
        response = requests.post(base_url, json=payload, headers=headers)

        # Handle the response and print the relevant output
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
