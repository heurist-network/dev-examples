const axios = require('axios');
const uuid = require('uuid');

function generateJobId() {
    return 'sdk_image_' + uuid.v4();
}

async function main() {
    const url = 'http://sequencer.heurist.xyz/submit_job';
    const apiKey = 'your_user_id#your_api_key';
    const modelId = 'YOUR_MODEL_ID';
    const payload = {
        job_id: generateJobId(),
        model_input: {
            SD: {
                prompt: 'A beautiful landscape with mountains and a river',
                neg_prompt: 'Avoid any signs of human presence',
                num_iterations: 20,
                width: 1024,
                height: 512,
                guidance_scale: 7.5,
                seed: -1
            }
        },
        model_id: modelId,
        deadline: 60,
        priority: 1
    };
    const headers = {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
    };

    console.log('Starting job submission...');
    console.log(`Generated job ID: ${payload.job_id}`);

    try {
        const response = await axios.post(url, payload, { headers });
        console.log(`Response status code: ${response.status}`);
        if (response.status === 200) {
            console.log('Job submitted successfully');
        } else {
            console.log(`Error submitting job: ${response.data}`);
        }

        console.log('Generated image URL:', response.data);
        return response.data;
    } catch (error) {
        console.error('Error submitting job:', error.message);
    }
}

main();
