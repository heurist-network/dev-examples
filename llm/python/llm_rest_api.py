import requests
from dotenv import load_dotenv
from openai import OpenAI

import os


def main():
    model = 'meta-llama/llama-3.3-70b-instruct'
    url = "https://llm-gateway.heurist.xyz/v1/chat/completions"
    load_dotenv()
    api_key = os.getenv("HEURIST_API_KEY")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "hello"
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print('Sending request to LLM API...')
    response = requests.request("POST", url, json=payload, headers=headers)
    
    print('Response status code:', response.status_code)
    response_json = response.json()
    
    print('LLM Response:', response_json['choices'][0]['message']['content'])
    
    if response.status_code != 200:
        print('Error:', response_json.get('error', 'Unknown error occurred'))

def use_openai_sdk():
    api_key = os.getenv("HEURIST_API_KEY")
    client = OpenAI(base_url='https://llm-gateway.heurist.xyz', api_key=api_key)
    model = 'meta-llama/llama-3.3-70b-instruct'
    print('Sending request to LLM API...')
    result = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": "hello"
        }],
        stream=False,
        temperature=0.5,
    )
    print('result: ', result.choices[0].message.content)


if __name__ == "__main__":
    use_openai_sdk()
