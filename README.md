# Heurist Integration Examples

### Supported Models:
The following open source models are supported. View the public model list [Supported Models](https://docs.heurist.ai/dev-guide/supported-models)
You can use the following model name as model_id in Heurist API/SDK.

For API Key please [Click Here](https://dev-api-form.heurist.ai/)

Heurist Official Documentation : [Click Here](https://docs.heurist.ai/introduction)

## Mesh Agent

The `telegram_group_agents` example demonstrates how to integrate multiple Heurist Mesh Agents into a Telegram bot. This example showcases:

### Supported Agents:
- **ExaSearchAgent**: Web search and question answering
- **ElfaTwitterIntelligenceAgent**: Twitter analysis and trending token tracking
- **FirecrawlSearchAgent**: Advanced web search and data extraction
- **SolWalletAgent**: Blockchain wallet analysis
- **TwitterInsightAgent**: Twitter follower history and mentions tracking


Check out the complete example in the [python/telegram_group_agents](python/telegram_group_agents) directory.


## Image Generation

[Image Generation Docs](https://docs.heurist.ai/dev-guide/image-generation/introduction)

For **SD (Stable Diffusion) image generation**, you can integrate using the **http://sequencer.heurist.xyz/submit_job** endpoint. This integration allows you to submit image generation jobs by specifying parameters such as **prompt**, **negative prompt**, **guidance scale**, **seed**, **num_iterations**, **width**, **height**, and **model_id**.


### Python Example Code:
- **generate_image_rest_api.py**: Demonstrates how to use the **REST API** to submit an image generation job to the **Sequencer** endpoint.
- **smartgen.py**: Demonstrates using **smartgen** for generative tasks in a Python environment.

### JavaScript Example Code:
- **generate_image_heurist_sdk.js**: Demonstrates using the **Heurist SDK** for image generation using the **REST API**.
- **generate_image_rest_api.py**: Demonstrates how to use the **REST API** to submit an image generation job to the **Sequencer** endpoint.
- **smartgen.js**: Demonstrates using **smartgen** for generative tasks in a JavaScript environment.

To generate images using the Heurist platform, you can either use the **REST API** or the **HEURIST SDK**.

## LLM Integration

[LLM Gateway Docs](https://docs.heurist.ai/dev-guide/llm-gateway/introduction)

For **LLM (Large Language Models)**, you can integrate using the **LLM Gateway**. This integration allows you to access and interact with various models, including using both the OpenAI SDK and the custom tool-calling features.

### Python Example Code:
- **llm_openai_sdk.py**: Demonstrates how to use the **OpenAI SDK** to generate text via the **LLM Gateway**, supporting both streaming and non-streaming modes.
- **llm_rest_api.py**: Demonstrates how to use the **REST API** to communicate with the **LLM Gateway** to generate text.
- **embedding_example.py**: Demonstrates how to use the **OpenAI SDK** to generate embeddings via the **LLM Gateway**.
- **tool-calling.py**: This example uses the Hermes Llama-3.1 model finetuned with tool-calling capabilities.




### JavaScript Example Code:
- **llm_openai_sdk.js**: Demonstrates how to use the **OpenAI SDK** to interact with the **LLM Gateway**.
- **llm_rest_api.js**: Demonstrates how to use the **REST API** to communicate with the **LLM Gateway**.
- **embedding_example.js**: Demonstrates how to generate embeddings using the **OpenAI SDK** with the **LLM Gateway**.
- **tool-calling.js**: This example uses the Hermes Llama-3.1 model finetuned with tool-calling capabilities.
