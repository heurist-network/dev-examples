const { OpenAI } = require('openai');

const client = new OpenAI({
  apiKey: "your_user_id#your_api_key",  // For API key, visit: https://dev-api-form.heurist.ai/
  baseURL: 'https://llm-gateway.heurist.xyz',
});

const modelId = 'HEURIST_MODEL_ID';  // For the supported model list, visit: https://github.com/heurist-network/heurist-models/blob/main/models.json

const msgs = [
  { role: 'system', content: 'You are a helpful assistant. Your output should be in CAPITAL LETTERS.' },
  { role: 'user', content: 'Write 3 short bullet points of the benefits of decentralized AI.' },
];

/**
 * Streams real-time responses from the OpenAI API using the provided messages.
 *
 * Args:
 * - messages (Array): An array of objects representing the conversation history. 
 *   Each object contains `role` (e.g., "system", "user") and `content`.
 * - temperature (number, optional): Controls the randomness of the output. Default is 0.75.
 * - maxTokens (number, optional): Maximum number of tokens to generate in the response. Default is 500.
 *
 * Functionality:
 * - Sends the conversation history to the API for generating a real-time response.
 * - Streams the response chunk by chunk and outputs the content in real time.
 * - Ends the stream once all chunks are received.
  */
async function testOpenAIAPIStream(messages, temperature = 0.75, maxTokens = 500) {
  try {
    const stream = await client.chat.completions.create({
      model: modelId,
      messages: messages,
      stream: true,
      temperature: temperature,
      max_tokens: maxTokens,
    });

    console.log('Response from OpenAI Streaming API:');
    for await (const chunk of stream) {
      if (chunk.choices && chunk.choices[0].delta && chunk.choices[0].delta.content) {
        process.stdout.write(chunk.choices[0].delta.content);
      }
    }
    console.log('\nStreaming ended.');
  } catch (error) {
    console.error('An error occurred during the streaming API call:', error);
  }
}

async function testOpenAIAPI(messages, temperature = 0.75, maxTokens = 500) {
  try {
    const result = await client.chat.completions.create({
      model: modelId,
      messages: messages,
      stream: false,
      temperature: temperature,
      max_tokens: maxTokens,
    });

    console.log('Response from OpenAI API:');
    console.log(result.choices[0].message.content);
  } catch (error) {
    console.error('An error occurred during the non-streaming API call:', error);
  }
}


async function main() {
  await testOpenAIAPIStream(msgs, 0.5, 200);
  // Uncomment the line below to test the non-streaming API with different temperature and maxTokens values
  // await testOpenAIAPI(msgs, 1.0, 500);
}

main();
