import os
from openai import OpenAI

# Load API key from environment variable
api_key = "your_user_id#your_api_key"
base_url = "https://llm-gateway.heurist.xyz"
client = OpenAI(api_key=api_key, base_url=base_url)

# Example input: can be a string or a list of strings (image prompts)
input = ["A beautiful landscape with mountains and rivers", "A futuristic city at sunset"]

# Call the embeddings API to generate embeddings for the SD model
embeddings = client.embeddings.create(
  model="HeuristLogo",          # Specify the SD model
  input=input,                  # Provide the image prompt
  encoding_format="float"       # Specify the encoding format
)

# If input is a string, print the corresponding embedding
if isinstance(input, str):
    print(embeddings.data[0].embedding)
else:
    # If input is a list, print the embeddings for each element
    for i in range(len(input)):
        print(f"Embedding for prompt '{input[i]}':")
        print(embeddings.data[i].embedding)

# Print token usage for the request
print("Prompt tokens used:", embeddings.usage.prompt_tokens)
