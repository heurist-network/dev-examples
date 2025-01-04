from openai import OpenAI
import json
from typing import Dict, Any

# You must use a model that supports tool calling (function calling)
model_id = "hermes-3-llama3.1-8b" 

# Configure the OpenAI client
client = OpenAI(
    api_key="your_user_id#your_api_key",  # for API key visit = https://dev-api-form.heurist.ai/
    base_url="https://llm-gateway.heurist.xyz"
)

def get_coin_price(token: str) -> float:
    """
    Simulates fetching the current price of a given cryptocurrency.
    In a real-world scenario, this would call an actual API.
    
    Args:
        token (str): The name or symbol of the cryptocurrency.
    
    Returns:
        float: The current price of the specified cryptocurrency in USD.
    """
    # For demonstration purposes, we're returning static prices
    # In practice, you'd call a real-time crypto price API here
    print("calling get_coin_price")
    prices = {
        "bitcoin": 45000.00,
        "ethereum": 3000.00,
        "dogecoin": 0.25,
    }
    return prices.get(token.lower(), 0.0)

def get_weather(city: str) -> Dict[str, Any]:
    """
    Simulates fetching the current weather for a given city.
    In a real-world scenario, this would call an actual weather API.
    
    Args:
        city (str): The name of the city.
    
    Returns:
        Dict[str, Any]: A dictionary containing weather information.
    """
    # For demonstration purposes, we're returning static weather data
    # In practice, you'd call a real weather API here
    print("calling get_weather")
    weathers = {
        "new york": {"temperature": 20, "condition": "Cloudy"},
        "london": {"temperature": 15, "condition": "Rainy"},
        "tokyo": {"temperature": 25, "condition": "Sunny"},
    }
    return weathers.get(city.lower(), {"temperature": 0, "condition": "Unknown"})

def format_price(price: float) -> str:
    """
    Formats the price with two decimal places and adds the USD symbol.
    
    Args:
        price (float): The price to format.
    
    Returns:
        str: Formatted price string.
    """
    return f"${price:.2f}"

# Define the tools
tools = [
    {
        'type': 'function',
        'function': {
            'name': 'get_coin_price',
            'description': 'Get the current price of a specified cryptocurrency in USD',
            'parameters': {
                'type': 'object',
                'properties': {
                    'token': {
                        'type': 'string',
                        'description': 'The name or symbol of the cryptocurrency',
                    },
                },
                'required': ['token'],
            },
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'description': 'Get the current weather for a specified city',
            'parameters': {
                'type': 'object',
                'properties': {
                    'city': {
                        'type': 'string',
                        'description': 'The name of the city',
                    },
                },
                'required': ['city'],
            },
        }
    }
]

def query_llm_with_tools(prompt: str) -> str:
    """
    Queries the LLM to get information about cryptocurrency prices or weather.
    
    Args:
        prompt (str): User's question about crypto prices or weather.
    
    Returns:
        str: LLM's response incorporating the requested information.
    """
    messages = [{'role': 'user', 'content': prompt}]
    
    # First API call to determine if we need to use a tool
    response = client.chat.completions.create(
        model=model_id,
        messages=messages,
        temperature=0.01,
        tools=tools,
        tool_choice="auto"
    )
    
    # Check if the model wants to use a tool
    if response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        # Call the appropriate function based on the tool choice
        if function_name == "get_coin_price":
            result = get_coin_price(function_args['token'])
            tool_response = format_price(result)
        elif function_name == "get_weather":
            result = get_weather(function_args['city'])
            tool_response = f"Temperature: {result['temperature']}°C, Condition: {result['condition']}"
        else:
            tool_response = "Unknown function called"
        
        # Add the tool response to the conversation
        messages.append(response.choices[0].message)
        messages.append({
            'role': 'tool',
            'content': tool_response,
            'tool_call_id': tool_call.id
        })
        
        # Second API call to generate the final response
        final_response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.01
        )
        
        return final_response.choices[0].message.content
    else:
        # If no tool was called, return the initial response
        return response.choices[0].message.content

# Example usage
if __name__ == "__main__":
    prompts = [
        "What's the current Bitcoin price?",
        "How's the weather in Tokyo?",
        "Write a joke within 50 words" # This should not call any tools
    ]
    
    for prompt in prompts:
        print(f"User: {prompt}")
        response = query_llm_with_tools(prompt)
        print(f"AI: {response}\n")