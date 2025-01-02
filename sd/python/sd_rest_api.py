import requests
import os
import uuid

def generate_job_id():
    return "sdk_image_" + str(uuid.uuid4())

def main():
    url = "http://sequencer.heurist.xyz/submit_job"
    api_key = "your_user_id#your_api_key"
    model_id = 'HeuristLogo'
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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print('Starting job submission...')
    print(f'Generated job ID: {payload["job_id"]}')
    
    response = requests.request("POST", url, json=payload, headers=headers)
    
    print(f'Response status code: {response.status_code}')
    if response.status_code == 200:
        print('Job submitted successfully')
    else:
        print(f'Error submitting job: {response.text}')
    
    print('Generated image URL:', response.text)
    return response.text

if __name__ == "__main__":
    main()