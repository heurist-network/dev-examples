async function main() {
    const url = "https://llm-gateway.heurist.xyz/v1/chat/completions";
    const apiKey = "your_user_id#your_api_key";
    
    const payload = {
        model: "YOUR_MODEL_ID",
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
