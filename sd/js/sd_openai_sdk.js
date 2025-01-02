const { v4: uuidv4 } = require('uuid');
const { OpenAI } = require('openai'); 

function generateJobId() {
    return "sdk_image_" + uuidv4();
}

async function main() {
    console.log('Starting image generation job...');

    // Initialize OpenAI client with the provided API key
    const client = new OpenAI({
        apiKey: "your_user_id#your_api_key",
        baseURL: 'https://llm-gateway.heurist.xyz',  // Make sure to adjust the URL if necessary
    });

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
        "model_id": "HeuristLogo",  // Make sure to use the correct model ID for image generation
        "deadline": 60,
        "priority": 1
    };

    console.log('Job ID:', payload.job_id);
    console.log('Submitting image generation job with OpenAI SDK...');

    try {
        // Call OpenAI SDK method for image generation (adjust for actual API endpoint)
        const response = await client.images.create({
            prompt: payload.model_input.SD.prompt,
            negative_prompt: payload.model_input.SD.neg_prompt,
            num_iterations: payload.model_input.SD.num_iterations,
            width: payload.model_input.SD.width,
            height: payload.model_input.SD.height,
            guidance_scale: payload.model_input.SD.guidance_scale,
            seed: payload.model_input.SD.seed,
        });

        // Assuming the response contains the image URL or image data
        console.log('Image generation successful. Response:', response);
        return response;
    } catch (error) {
        console.error('Failed to generate image:', error.message);
        throw error;
    }
}

if (require.main === module) {
    main().catch(console.error);
}
