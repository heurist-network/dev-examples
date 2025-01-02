(async () => {
    const fetch = (await import('node-fetch')).default; 
    
    const apiKey = 'your_user_id#your_api_key';
    const baseUrl = 'https://llm-gateway.heurist.xyz';
    const model_id = 'hermes-3-llama3.1-8b';
  
    // Simulated tool functions
    function getCoinPrice(token) {
      const prices = {
        bitcoin: 45000.00,
        ethereum: 3000.00,
        dogecoin: 0.25,
      };
      console.log('Calling get_coin_price');
      return prices[token.toLowerCase()] || 0.0;
    }
  
    function getWeather(city) {
      const weathers = {
        'new york': { temperature: 20, condition: 'Cloudy' },
        'london': { temperature: 15, condition: 'Rainy' },
        'tokyo': { temperature: 25, condition: 'Sunny' },
      };
      console.log('Calling get_weather');
      return weathers[city.toLowerCase()] || { temperature: 0, condition: 'Unknown' };
    }
  
    function formatPrice(price) {
      return `$${price.toFixed(2)}`;
    }
  
    // Define the tools
    const tools = [
      {
        type: 'function',
        function: {
          name: 'get_coin_price',
          description: 'Get the current price of a specified cryptocurrency in USD',
          parameters: {
            type: 'object',
            properties: {
              token: {
                type: 'string',
                description: 'The name or symbol of the cryptocurrency',
              },
            },
            required: ['token'],
          },
        },
      },
      {
        type: 'function',
        function: {
          name: 'get_weather',
          description: 'Get the current weather for a specified city',
          parameters: {
            type: 'object',
            properties: {
              city: {
                type: 'string',
                description: 'The name of the city',
              },
            },
            required: ['city'],
          },
        },
      },
    ];
  
    // API request function
    async function queryLLMWithTools(prompt) {
      const messages = [{ role: 'user', content: prompt }];
      
      const requestPayload = {
        model: model_id,
        messages,
        temperature: 0.01,
        tools,
        tool_choice: 'auto',
      };
  
      // First API call to determine if we need to use a tool
      let response = await fetch(`${baseUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestPayload),
      });
      let responseJson = await response.json();
  
      if (responseJson.choices[0].message.tool_calls) {
        const toolCall = responseJson.choices[0].message.tool_calls[0];
        const functionName = toolCall.function.name;
        const functionArgs = JSON.parse(toolCall.function.arguments);
  
        let toolResponse;
  
        if (functionName === 'get_coin_price') {
          const result = getCoinPrice(functionArgs.token);
          toolResponse = formatPrice(result);
        } else if (functionName === 'get_weather') {
          const result = getWeather(functionArgs.city);
          toolResponse = `Temperature: ${result.temperature}°C, Condition: ${result.condition}`;
        } else {
          toolResponse = 'Unknown function called';
        }
  
        messages.push(responseJson.choices[0].message);
        messages.push({
          role: 'tool',
          content: toolResponse,
          tool_call_id: toolCall.id,
        });
  
        // Second API call to generate the final response
        response = await fetch(`${baseUrl}/v1/chat/completions`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            model: model_id,
            messages,
            temperature: 0.01,
          }),
        });
        responseJson = await response.json();
        return responseJson.choices[0].message.content;
      } else {
        return responseJson.choices[0].message.content;
      }
    }
  
    // Example usage
    async function runExample() {
      const prompts = [
        "What's the current Bitcoin price?",
        "How's the weather in Tokyo?",
        "Write a joke within 50 words", // This should not call any tools
      ];
  
      for (const prompt of prompts) {
        console.log(`User: ${prompt}`);
        const response = await queryLLMWithTools(prompt);
        console.log(`AI: ${response}\n`);
      }
    }
  
    runExample();
  })();
  