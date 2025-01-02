const { OpenAI } = require('openai');  

const client = new OpenAI({
  apiKey: "your_user_id#your_api_key",
  baseURL: 'https://llm-gateway.heurist.xyz',
});

const input = ['hello', 'world']; 

async function generateEmbeddings() {
  try {
    const embeddings = await client.embeddings.create({
      model: 'YOUR_MODEL_ID',           // Specify the model
      input: input,                     // Provide the input text
      encoding_format: 'float',         // Specify the encoding format
    });

    if (typeof input === 'string') {
      console.log(embeddings.data[0].embedding);
    } else {
      // If input is an array, loop through and print each embedding
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
