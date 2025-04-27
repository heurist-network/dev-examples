/**
 * Send a POST request to the LLM API for generating a response based on user input.
 *
 * Args:
 * - url (string): The API endpoint for sending chat completion requests.
 * - apiKey (string): The API key for authentication.
 * - payload (object): The request payload containing:
 *   - model (string): Specifies the model ID.
 *   - messages (array): An array of messages in the format { role: string, content: string }.
 * 
 * Functionality:
 * - Constructs the payload for the API request with the user-provided input.
 * - Sends a POST request to the LLM API with appropriate headers and payload.
 * - Logs the request payload and response details, including the generated AI content.
 */

async function main() {
    const url = "https://llm-gateway.heurist.xyz/v1/chat/completions";
    const apiKey = "your_user_id#your_api_key";  // For API key, visit: https://dev-api-form.heurist.ai/
    
    const payload = {
        model: "HEURIST_MODEL_ID",  // For supported models, visit: https://docs.heurist.ai/dev-guide/supported-models
        messages: [
            {
                role: "user",
                content: "hello"
            }
        ]
    };

    const headers = {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
    };

    console.log('Starting API request...');
    console.log('Request payload:', payload);

    try {
        console.log('Sending request to LLM API...');
        
        const response = await fetch(url, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });

        console.log('Response status:', response.status);
        
        if (response.ok) {
            const responseJson = await response.json();
            console.log('Complete response:', responseJson);
            console.log('LLM response content:', responseJson.choices[0].message.content);
        } else {
            console.error('API request failed with status:', response.status);
        }
    } catch (error) {
        console.error('API request failed:', error.message);
    }
}

main();
