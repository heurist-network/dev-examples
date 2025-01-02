require('dotenv').config();
const { OpenAI } = require('openai');

const client = new OpenAI({
  apiKey: "your_user_id#your_api_key",
  baseURL: 'https://llm-gateway.heurist.xyz',
});

const input = [
  'A beautiful landscape with mountains and rivers',
  'A futuristic city at sunset',
];  // Example input: list of image prompts

async function generateEmbeddings() {
  try {
    const embeddings = await client.embeddings.create({
      model: 'HeuristLogo',          // Specify the Stable Diffusion model
      input: input,                  // Provide the input prompts
      encoding_format: 'float',      // Specify the encoding format
    });

    if (typeof input === 'string') {
      console.log(embeddings.data[0].embedding);  // Print embedding if input is a single string
    } else {
      // If input is a list, loop through and print the embeddings for each prompt
      input.forEach((text, index) => {
        console.log(`Embedding for prompt '${text}':`);
        console.log(embeddings.data[index].embedding);
      });
    }

    console.log('Prompt tokens used:', embeddings.usage.prompt_tokens);  // Print token usage
  } catch (error) {
    console.error('Error generating embeddings:', error);
  }
}

generateEmbeddings();
