# Heurist Integration Examples

## Image Generation

- **Option 1**: [Use REST API](https://docs.heurist.ai/dev-guide/api-reference/image-generation/introduction)
- **Option 2**: [Use Node.js SDK with OpenAI](https://docs.heurist.ai/dev-guide/api-reference/heurist-sdk/basic-image-generation)

To generate images using the Heurist platform, you can either use the **REST API** or the **OpenAI SDK**. 

## Sd Integration

[SD Docs](https://docs.heurist.ai/dev-guide/image-generation/introduction)

For **SD (Stable Diffusion) image generation**, you can integrate using the **http://sequencer.heurist.xyz/submit_job** endpoint. This integration allows you to submit image generation jobs by specifying parameters such as **prompt**, **negative prompt**, **guidance scale**, **seed**, **num_iterations**, **width**, **height**, and **model_id**.


## LLM Integration

[LLM Gateway Docs](https://docs.heurist.ai/dev-guide/llm-gateway/introduction)

For **LLM (Large Language Models)**, you can integrate using the **LLM Gateway**. This integration allows you to access and interact with various models, including using both the OpenAI SDK and the custom tool-calling features.

### Example Code
- **`llm-gateway-openai-sdk.py`**: This Python example demonstrates using the `openai` SDK to generate text via the LLM Gateway, supporting both streaming and non-streaming modes.
- **`tool-calling.py`**: This example uses the Llama-3.1 model with tool-calling capabilities.
