const { OpenAI } = require('openai'); 

const client = new OpenAI({
  apiKey: "your_user_id#your_api_key",
  baseURL: 'https://llm-gateway.heurist.xyz',
});

const modelId = 'YOUR_MODEL_ID';

// Pre-defined messages to set the context for the AI model
const msgs = [
  { role: 'system', content: 'You are a helpful assistant. Your output should be in CAPITAL LETTERS.' },
  { role: 'user', content: 'Write 3 short bullet points of the benefits of decentralized AI.' },
];

// Streaming function: receives a real-time response from the AI model
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

// Non-streaming function: waits for the full response from the AI model
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

// Example usage of the streaming and non-streaming functions
async function main() {
  await testOpenAIAPIStream(msgs, 0.5, 200);
  // Uncomment the line below to test the non-streaming API with different temperature and maxTokens values
  // await testOpenAIAPI(msgs, 1.0, 500);
}

main();
