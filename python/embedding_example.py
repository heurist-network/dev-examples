from openai import OpenAI
"""
Demonstrates the use of the Heurist API to generate embeddings for input text.

Args:
- api_key (str): The API key required for authentication with the Heurist API.
- base_url (str): The base URL for the Heurist API endpoint.
- input (list or str): A list of strings or a single string for which embeddings will be generated.

Functionality:
- Creates embeddings for the provided input text using a specified model.
- Prints the embedding for each input item if the input is a list.
- Displays the number of prompt tokens used in the request.
"""


api_key = "your_user_id#your_api_key"  # For API key, visit: https://dev-api-form.heurist.ai/
base_url = "https://llm-gateway.heurist.xyz"
client = OpenAI(api_key=api_key, base_url=base_url)

input = ["hello", "world"]

embeddings = client.embeddings.create(
    model="BAAI/bge-large-en-v1.5",  # For the supported model list, visit: https://docs.heurist.ai/dev-guide/supported-models
    input=input,
    encoding_format="float"
)

if isinstance(input, str):
    print(embeddings.data[0].embedding)
else:
    # If input is a list, print the embeddings for each element
    for i in range(len(input)):
        print(f"Embedding for '{input[i]}':")
        print(embeddings.data[i].embedding)

print("Prompt tokens used:", embeddings.usage.prompt_tokens)
