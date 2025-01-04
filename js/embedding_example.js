const { OpenAI } = require('openai');  

/**
 * Demonstrates the use of the Heurist API to generate embeddings for input text.
 
 * Args:
 * - apiKey (string): The API key required for authentication. 
 * - baseURL (string): The base URL for the Heurist API endpoint.
 * - input (string or array): A single string or an array of strings for which embeddings will be generated.
 *
 * Functionality:
 * - Generates embeddings for the provided input using the specified AI model.
 * - Logs the embedding for each input item if the input is an array.
 * - Displays the number of prompt tokens used during the process.
 
 * API Reference:
 * - model (string): Specifies the model to use for generating embeddings. 
 * - encoding_format (string): Specifies the format of the generated embeddings, e.g., 'float'.
 */


const client = new OpenAI({
  apiKey: "your_user_id#your_api_key",  // For API key, visit: https://dev-api-form.heurist.ai/
  baseURL: 'https://llm-gateway.heurist.xyz',
});
const input = ['hello', 'world'];

async function generateEmbeddings() {
  try {
    const embeddings = await client.embeddings.create({
      model: 'BAAI/bge-large-en-v1.5',          // For supported models, visit: https://github.com/heurist-network/heurist-models/blob/main/models.json
      input: input,
      encoding_format: 'float',
    });

    if (typeof input === 'string') {
      console.log(embeddings.data[0].embedding);
    } else {
      input.forEach((text, index) => {
        console.log(`Embedding for '${text}':`);
        console.log(embeddings.data[index].embedding);
      });
    }

    console.log('Prompt tokens used:', embeddings.usage.prompt_tokens);
  } catch (error) {
    console.error('Error generating embeddings:', error);
  }
}

generateEmbeddings();
