import Heurist from 'heurist';

/**
 * Generates an image using the Heurist API.
 
 * Args:
 * - model (string): The model ID to use for image generation.
 * - prompt (string): The text prompt describing the desired image.
 * - width (number): The width of the generated image in pixels.
 * - height (number): The height of the generated image in pixels.
 
 * Functionality:
 * - Sends a request to the Heurist API to generate an image based on the given prompt and dimensions.
 * - Logs the generated image URL if successful.
 
 * Usage:
 * - Update the `apiKey` and `model` fields with appropriate values.
 * - Modify the `prompt`, `width`, and `height` as needed to customize the image generation request.
 */

const heurist = new Heurist({
  apiKey: "your_user_id#your_api_key",  // for API key visit = https://dev-api-form.heurist.ai/
});

async function main() {
  console.log('Starting image generation...');
  try {
    const response = await heurist.images.generate({
      model: 'HEURIST_MODEL_ID',  // support model list = https://github.com/heurist-network/heurist-models/blob/main/models.json
      prompt: 'a apple',    
      width: 512,           
      height: 512        
    });

    const { url } = response;
    console.log('Image generation successful!');
    console.log('Generated image URL:', url);
  } catch (error) {
    console.error('Error generating image:', error.message);
  }
}

main();
