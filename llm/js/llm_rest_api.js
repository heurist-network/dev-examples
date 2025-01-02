require('dotenv').config();


async function main() {
    console.log('Starting API request...');
    const url = "https://llm-gateway.heurist.xyz/v1/chat/completions";
    const apiKey = "your_user_id#your_api_key"

    const payload = {
        model: "dolphin-2.9-llama3-8b",
        messages: [
            {
                role: "user",
                content: "hello"
            }
        ]
    };
    console.log('Request payload:', payload);

    const headers = {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
    };

    try {
        console.log('Sending request to LLM API...');
        const response = await fetch(url, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });

        console.log('Response status:', response.status);
        const responseJson = await response.json();
        console.log('Complete response:', responseJson);
        console.log('LLM response content:', responseJson.choices[0].message.content);
    } catch (error) {
        console.error('API request failed:', error.message);
    }
}

main();