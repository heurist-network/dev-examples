import os
from openai import OpenAI
import uuid

# Function to generate a unique job ID
def generate_job_id():
    return "sdk_image_" + str(uuid.uuid4())

# Main function to interact with OpenAI API using SDK
def main():
    api_key = "your_user_id#your_api_key" 
    base_url = "https://llm-gateway.heurist.xyz"

    # Initialize OpenAI client with API key and base URL
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Define the model ID and job parameters
    model_id = 'FLUX.1-dev'
    payload = {
        "job_id": generate_job_id(),
        "model_input": {
            "SD": {
                "prompt": "A beautiful landscape with mountains and a river",
                "neg_prompt": "Avoid any signs of human presence",
                "num_iterations": 20,
                "width": 1024,
                "height": 512,
                "guidance_scale": 7.5,
                "seed": -1
            }},
        "model_id": model_id,
        "deadline": 60,
        "priority": 1
    }

    try:
        # Submit the job using the OpenAI SDK (this is the equivalent of sending the job via REST API)
        response = client.jobs.create(
            model=model_id,
            input=payload
        )

        # Handle the response and print the relevant output
        print(f"Generated job ID: {payload['job_id']}")
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print('Job submitted successfully')
        else:
            print(f"Error submitting job: {response.text}")
        
        print(f"Generated image URL: {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
