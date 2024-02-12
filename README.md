# API Usage Examples

## Stable Diffusion

[Developer Docs](https://docs.heurist.xyz/integration/stable-diffusion-api)

- [Stable Diffusion WebUI](https://github.com/heurist-network/stable-diffusion-webui) is a simple demo project that integrates with Heurist's image generation API, built with [Gradio](https://www.gradio.app/) in Python. Here's the relevant [POST API request](https://github.com/heurist-network/stable-diffusion-webui/blob/master/main.py#L36)
- [Imagine](https://github.com/heurist-network/imagine) is a production-ready AI image generator site built with React and Next.js. Its [getImage API route](https://github.com/heurist-network/imagine/blob/main/pages/api/getImage.js) demonstrates the usage of Stable Diffusion API in real world.

## LLM
[Developer Docs](https://docs.heurist.xyz/integration/heurist-llm-gateway)

- `llm-gateway-openai-sdk.py` is an example of using Python `openai` SDK to generate texts. Both stream and non-stream modes are supported.