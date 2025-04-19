const axios = require('axios');
require('dotenv').config();

class APIError extends Error {
    constructor(message, statusCode = null) {
        super(message);
        this.statusCode = statusCode;
    }
}

class SmartGen {
    constructor(apiKey, baseUrl = process.env.HEURIST_SEQUENCER_URL) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this._session = null;
    }

    async _createSession() {
        if (!this._session) {
            this._session = axios.create({
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json',
                }
            });
        }
    }

    async _closeSession() {
        if (this._session) {
            this._session = null;
        }
    }

    async _ensureSession() {
        if (!this._session) {
            await this._createSession();
        }
    }

    async generateImage({
        description,
        imageModel = 'FLUX.1-dev',
        width = 1024,
        height = 768,
        stylizationLevel = null,
        detailLevel = null,
        colorLevel = null,
        lightingLevel = null,
        mustInclude = null,
        quality = 'normal',
        paramOnly = false
    }) {
        try {
            await this._ensureSession();

            // Generate a random job ID
            const jobId = `sdk-image-${Math.random().toString(36).substring(2, 12)}`;

            // Prepare model input parameters
            const modelInput = {
                prompt: description,
                width: width,
                height: height,
            };

            if (stylizationLevel !== null) modelInput.stylizationLevel = stylizationLevel;
            if (detailLevel !== null) modelInput.detailLevel = detailLevel;
            if (colorLevel !== null) modelInput.colorLevel = colorLevel;
            if (lightingLevel !== null) modelInput.lightingLevel = lightingLevel;
            if (mustInclude) modelInput.mustInclude = mustInclude;

            // Prepare the full request parameters
            const params = {
                job_id: jobId,
                model_input: {
                    SD: modelInput
                },
                model_type: 'SD',
                model_id: imageModel,
                deadline: 30,
                priority: 1
            };

            if (paramOnly) {
                return { parameters: params };
            }

            // Generate the image
            const response = await this._session.post(`${this.baseUrl}/submit_job`, params);
            if (response.status !== 200) {
                throw new APIError(`Generate image error: ${response.status} ${response.data}`);
            }

            let url = response.data;
            // Remove quotes from the URL if present
            url = url.replace(/^"(.*)"$/, '$1');

            return {
                url: url,
                parameters: modelInput
            };

        } catch (e) {
            if (e instanceof APIError) {
                throw e;
            }
            throw new APIError(`Failed to generate image: ${e.message}`);
        }
    }
}

module.exports = SmartGen;
