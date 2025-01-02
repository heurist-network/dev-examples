const { v4: uuidv4 } = require('uuid');

function generateJobId() {
    return "sdk_image_" + uuidv4();
}

async function main() {
    console.log('Starting image generation job...');
    const url = "http://sequencer.heurist.xyz/submit_job";
    const apiKey = "your_user_id#your_api_key";

    const payload = {
        "job_id": generateJobId(),
        "model_input": {
            "SD": {
                "prompt": "A beautiful landscape with mountains and a river",
                "neg_prompt": "Avoid any signs of human presence",
                "num_iterations": 20,
                "width": 1024,
                "height": 512,
                "guidance_scale": 7.5,
                "seed": -1
            }
        },
        "model_id": "HeuristLogo",
        "deadline": 60,
        "priority": 1
    };

    console.log('Job ID:', payload.job_id);
    console.log('Submitting request to:', url);

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                "Authorization": `Bearer ${apiKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            console.error('Request failed with status:', response.status);
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Request successful. Response:', data);
        return data;
    } catch (error) {
        console.error('Failed to generate image:', error.message);
        throw error;
    }
}

if (require.main === module) {
    main().catch(console.error);
}