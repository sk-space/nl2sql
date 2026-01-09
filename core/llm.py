import logging
import os

import torch
from dotenv import load_dotenv
from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModel, AutoTokenizer, pipeline
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)


class HuggingFaceClientWrapper:
    """Wrapper to make HuggingFace API compatible with LangChain interface"""

    def __init__(self):
        self.client = OpenAI(
            base_url=os.environ["HF_API_URL"],
            api_key=os.environ["HF_TOKEN"],
        )
        self._model_name = os.getenv("HF_MODEL_NAME")

    def invoke(self, prompt):
        """Implement the invoke method for LangChain compatibility"""
        try:
            completion = self.client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=150,
                temperature=0.1
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.info(f"Error calling HuggingFace API: {e}")
            raise e

    def __call__(self, prompt):
        """Support for direct calling"""
        return self.invoke(prompt)


class HFInferenceClient:

    def __init__(self):
        self.use_api = True
        self._model_name = os.getenv("HF_MODEL_NAME")

    def load_model(self):
        """Load the model either via HuggingFace API or locally"""
        if self.use_api:
            return self._load_huggingface_api_model()
        else:
            return self._load_local_model()


    def _load_huggingface_api_model(self):
        """Load model using HuggingFace API (recommended)"""
        logger.info("Loading model via HuggingFace API: {self._model_name}")

        # Check if HF_TOKEN is available
        if not os.getenv("HF_TOKEN"):
            logger.info("Warning: HF_TOKEN not found in environment variables. Using fallback.")

        try:
            return HuggingFaceClientWrapper()
        except Exception as e:
            logger.info("Error loading model via API: {e}")


    def _load_local_model(self):
        """Load the HuggingFace model locally with fallbacks"""
        try:
            logger.info("Loading local model: {self._model_name}")

            tokenizer = AutoTokenizer.from_pretrained(self._model_name)

            # Add padding token if it doesn't exist
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModel.from_pretrained(
                self._model_name,
                torch_dtype=torch.bfloat16,
                low_cpu_mem_usage=True
            )

            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=150,
                temperature=0.1,
                top_p=0.95,
                repetition_penalty=1.15,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )

            logger.info("Local model loaded successfully")

            return HuggingFacePipeline(pipeline=pipe)

        except Exception as e:
            logger.info("Error loading local model: {self._model_name}: {e}")


# Create global instance
hf_interface = HFInferenceClient()
