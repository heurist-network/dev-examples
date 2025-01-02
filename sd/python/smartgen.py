from typing import Dict, Any, Optional
import aiohttp
import secrets
import os
from dotenv import load_dotenv

load_dotenv()

class APIError(Exception):
    """Raised when the API returns an error response."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

class PromptEnhancementError(Exception):
    """Raised when there's an error enhancing a prompt."""
    pass

class SmartGen:
    def __init__(self, api_key: str, base_url: str = os.getenv("HEURIST_SEQUENCER_URL")):
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session()

    async def _create_session(self):
        """Create aiohttp session if it doesn't exist."""
        if self._session is None:
            self._session = aiohttp.ClientSession(headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })

    async def _close_session(self):
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _ensure_session(self):
        """Ensure session exists before making requests."""
        if self._session is None:
            await self._create_session()

    async def generate_image(
        self,
        description: str,
        image_model: str = "FLUX.1-dev",
        width: int = 1024,
        height: int = 768,
        stylization_level: Optional[int] = None,
        detail_level: Optional[int] = None,
        color_level: Optional[int] = None,
        lighting_level: Optional[int] = None,
        must_include: Optional[str] = None,
        quality: str = "normal",
        param_only: bool = False
    ) -> Dict[str, Any]:
        try:
            await self._ensure_session()
            
            # Generate a random job ID using secrets module
            job_id = f"sdk-image-{secrets.token_hex(5)}"  # 5 bytes = 10 hex characters

            # Prepare model input parameters
            model_input = {
                "prompt": description,
                "width": width,
                "height": height,
            }

            if stylization_level is not None:
                model_input["stylization_level"] = stylization_level
            if detail_level is not None:
                model_input["detail_level"] = detail_level
            if color_level is not None:
                model_input["color_level"] = color_level
            if lighting_level is not None:
                model_input["lighting_level"] = lighting_level
            if must_include:
                model_input["must_include"] = must_include

            # Prepare the full request parameters
            params = {
                "job_id": job_id,
                "model_input": {
                    "SD": model_input
                },
                "model_type": "SD",
                "model_id": image_model,
                "deadline": 30,
                "priority": 1
            }

            if param_only:
                return {"parameters": params}

            # Generate the image
            async with self._session.post(
                f"{self.base_url}/submit_job",
                json=params
            ) as response:
                if response.status != 200:
                    raise APIError(f"Generate image error: {response.status} {await response.text()}")
                
                url = await response.text()
                # Remove quotes from the URL if present
                url = url.strip('"')
                
                return {
                    "url": url,
                    "parameters": model_input
                }

        except Exception as e:
            if isinstance(e, (PromptEnhancementError, APIError)):
                raise e
            raise APIError(f"Failed to generate image: {str(e)}") 