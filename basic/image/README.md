# Image Generation Examples

This folder contains examples for generating images using Stable Diffusion models through Heurist's Sequencer endpoint.

## Prerequisites
- Heurist API Key ([Get one here](https://dev-api-form.heurist.ai/))
- Node.js (for JavaScript examples)
- Python 3.8+ (for Python examples)

## Examples

### JavaScript
- `generate_image_heurist_sdk.js` - Generate images using the Heurist SDK
- `generate_image_rest_api.js` - Generate images using the REST API
- `smartgen.js` - SmartGen for enhanced image generation

### Python
- `generate_image_rest_api.py` - Generate images using the REST API
- `smartgen.py` - SmartGen for enhanced image generation

## Getting Started

### JavaScript
```bash
npm install axios
node generate_image_rest_api.js
```

### Python
```bash
pip install requests python-dotenv aiohttp
python generate_image_rest_api.py
```

## Customization Parameters
You can customize image generation with these parameters:
- `prompt` - Text description of the desired image
- `negative_prompt` - Elements to avoid in the generated image
- `guidance_scale` - Higher values adhere more closely to the prompt
- `seed` - For reproducible results (use -1 for random)
- `num_iterations` - Number of diffusion steps
- `width` & `height` - Image dimensions
- `model_id` - Specific model to use

## Documentation
- [Image Generation Documentation](https://docs.heurist.ai/dev-guide/image-generation/introduction)
- [Supported Image Models](https://docs.heurist.ai/dev-guide/supported-models)