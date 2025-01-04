const axios = require('axios');
const uuid = require('uuid');

/**
 * Submits a job to the Heurist API for generating an image based on the provided input.
 *
 * Args:
 * - url (string): The API endpoint for job submission.
 * - apiKey (string): The API key for authentication.
 * - modelId (string): The model ID to use for image generation.
 * - payload (object): The request payload containing:
 *   - job_id (string): A unique job ID generated using the UUID library.
 *   - model_input (object): Includes the image generation parameters:
 *     - prompt (string): Description of the desired image.
 *     - neg_prompt (string): Description of elements to avoid in the image.
 *     - num_iterations (number): Number of iterations for refining the image.
 *     - width (number): Width of the image in pixels.
 *     - height (number): Height of the image in pixels.
 *     - guidance_scale (number): Guidance scale for fine-tuning the output.
 *     - seed (number): Random seed for image generation (-1 for random seed).
 *   - model_id (string): Specifies the model ID.
 *   - deadline (number): Deadline for job completion in seconds.
 *   - priority (number): Priority level of the job.
 *
 * Functionality:
 * - Generates a unique job ID.
 * - Constructs a payload with image generation details and submits it to the Heurist API.
 * - Logs the job ID, response status, and the generated image URL upon success.
 *
 */

function generateJobId() {
    return 'sdk_image_' + uuid.v4();
}

async function main() {
    const url = 'http://sequencer.heurist.xyz/submit_job';  
    const apiKey = 'your_user_id#your_api_key';   // For API key, visit: https://dev-api-form.heurist.ai/
    const modelId = 'HEURIST_MODEL_ID';  // For the supported model list, visit: https://github.com/heurist-network/heurist-models/blob/main/models.json

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
