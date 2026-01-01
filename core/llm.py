import logging
import re
from typing import Optional, Tuple, List, Dict

import requests

from core.config import config

# Setup logging
logger = logging.getLogger(__name__)


class HFInferenceClient:
    """Client for HuggingFace Inference API"""

    def __init__(self):
        self.base_url = config.HF_API_URL
        self.headers = {
            "Authorization": f"Bearer {config.HF_API_TOKEN}",
            "Content-Type": "application/json"
        }
        self.current_model = config.HF_MODEL

    def get_available_models(self) -> List[Dict]:
        """Get available models from the router"""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get models: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []

    def find_best_model(self, task: str = "text-generation") -> Optional[str]:
        """Find the best available model for a task"""
        try:
            models = self.get_available_models()
            if not models:
                return config.HF_MODEL

            # Filter for text generation models
            text_gen_models = [
                model for model in models
                if task in model.get("tags", [])
            ]

            if text_gen_models:
                # Sort by likes/downloads
                text_gen_models.sort(
                    key=lambda x: x.get("likes", 0) + x.get("downloads", 0),
                    reverse=True
                )
                return text_gen_models[0]["id"]

            return config.HF_MODEL
        except Exception as e:
            logger.error(f"Error finding best model: {e}")
            return config.HF_MODEL

    def generate_text(self,
                      prompt: str,
                      model: Optional[str] = None,
                      max_tokens: int = 300,
                      temperature: float = 0.3) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate text using HuggingFace Inference API

        Args:
            prompt: Input prompt
            model: Model to use (None for auto-selection)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (generated_text, error_message)
        """
        if not model:
            model = self.current_model

        try:
            # Prepare request payload
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.95,
                    "do_sample": True,
                    "return_full_text": False
                },
                "options": {
                    "use_cache": True,
                    "wait_for_model": True
                }
            }

            # Make API request
            response = requests.post(
                f"{self.base_url}/chat/completions",  # Updated endpoint for chat
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                # Handle different response formats
                if isinstance(result, list):
                    # Old format: [{"generated_text": "..."}]
                    generated_text = result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    # Chat completion format
                    if "choices" in result:
                        generated_text = result["choices"][0].get("message", {}).get("content", "")
                    elif "generated_text" in result:
                        generated_text = result["generated_text"]
                    else:
                        generated_text = str(result)
                else:
                    generated_text = str(result)

                return generated_text.strip(), None

            else:
                error_msg = f"API Error {response.status_code}: {response.text}"
                logger.error(error_msg)

                # Try fallback models if primary fails
                if response.status_code in [401, 403, 404]:
                    return self._try_fallback_models(prompt, max_tokens, temperature)

                return None, error_msg

        except requests.exceptions.Timeout:
            error_msg = "Request timeout - model might be busy"
            logger.error(error_msg)
            return None, error_msg

        except Exception as e:
            error_msg = f"Generation failed: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    def _try_fallback_models(self, prompt: str, max_tokens: int, temperature: float) -> Tuple[
        Optional[str], Optional[str]]:
        """Try fallback models if primary fails"""
        for model_id in config.FALLBACK_MODELS:
            if model_id != self.current_model:
                print(f"🔄 Trying fallback model: {model_id}")
                result, error = self.generate_text(prompt, model_id, max_tokens, temperature)
                if result:
                    self.current_model = model_id
                    return result, None

        return None, "All models failed"

    def test_connection(self) -> bool:
        """Test connection to HuggingFace API"""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False


class LLMService:
    def __init__(self):
        self.client = HFInferenceClient()
        self.connected = False
        self._test_connection()

    def _test_connection(self):
        """Test API connection"""
        print("🔌 Testing HuggingFace API connection...")
        self.connected = self.client.test_connection()
        if self.connected:
            print("✅ Connected to HuggingFace Inference API")

            # Find best available model
            best_model = self.client.find_best_model()
            if best_model != config.HF_MODEL:
                print(f"🔀 Using best available model: {best_model}")
                self.client.current_model = best_model
            else:
                print(f"📝 Using configured model: {config.HF_MODEL}")
        else:
            print("❌ Cannot connect to HuggingFace API")
            print("   Please check your HF_API_TOKEN and internet connection")

    def is_available(self) -> bool:
        """Check if LLM service is available"""
        return self.connected

    def generate_sql(self, prompt: str, max_tokens: int = 400) -> Tuple[Optional[str], Optional[str]]:
        """Generate SQL from natural language prompt"""
        if not self.is_available():
            return None, "LLM service not available"

        # Enhance prompt for better SQL generation
        enhanced_prompt = self._enhance_sql_prompt(prompt)

        # Generate using API
        generated_text, error = self.client.generate_text(
            enhanced_prompt,
            max_tokens=max_tokens,
            temperature=0.2  # Lower temperature for more deterministic SQL
        )

        if error:
            return None, error

        # Extract SQL from generated text
        sql = self._extract_sql(generated_text)
        return sql, None

    def _enhance_sql_prompt(self, prompt: str) -> str:
        """Enhance prompt for better SQL generation"""
        return f"""You are an expert SQL developer. Convert the following natural language query to SQL.

Rules:
1. Output ONLY the SQL query, no explanations
2. Use proper SQL syntax
3. Use LIMIT for large result sets
4. Include WHERE clauses when filtering
5. Use JOINs when accessing multiple tables

Natural Language Query: {prompt}

SQL Query:"""

    def _extract_sql(self, text: str) -> str:
        """Extract clean SQL from generated text"""
        # Remove markdown code blocks
        text = re.sub(r'```sql\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        text = re.sub(r'^`', '', text)
        text = re.sub(r'`$', '', text)

        # Find SQL statement
        lines = text.strip().split('\n')
        sql_lines = []
        in_sql = False

        for line in lines:
            line_stripped = line.strip()
            line_upper = line_stripped.upper()

            # Check if this looks like SQL
            if any(line_upper.startswith(keyword) for keyword in
                   ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'WITH']):
                in_sql = True

            if in_sql:
                # Stop if we hit explanation text
                if line_stripped and not line_stripped.startswith(('--', '/*', '*/')) and not any(
                        keyword in line_upper for keyword in
                        ['SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'LIMIT', ';']
                ):
                    if sql_lines and line_stripped:  # We have SQL and this isn't empty
                        # Check if it looks like natural language
                        if len(line_stripped.split()) > 8:  # Long line might be explanation
                            break

                if line_stripped:  # Add non-empty lines
                    sql_lines.append(line_stripped)

                    # Stop if we have a semicolon
                    if line_stripped.endswith(';'):
                        break

        if not sql_lines:
            # Try regex patterns
            patterns = [
                r'(SELECT.*?;)',
                r'(WITH.*?;)',
                r'```sql\s*(.*?)\s*```',
                r'(SELECT.*?)(?:\n\n|\Z)'
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    sql = match.group(1).strip()
                    if not sql.endswith(';'):
                        sql += ';'
                    return sql

            return text.strip()

        sql = ' '.join(sql_lines).strip()

        # Ensure proper SQL formatting
        if not sql.endswith(';'):
            sql += ';'

        return sql

    def chat_completion(self, messages: List[Dict[str, str]]) -> Tuple[Optional[str], Optional[str]]:
        """Chat completion using the API"""
        if not self.is_available():
            return None, "LLM service not available"

        try:
            # Prepare chat messages
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

            # Make chat completion request
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.client.headers,
                json={
                    "model": self.client.current_model,
                    "messages": formatted_messages,
                    "max_tokens": 500,
                    "temperature": 0.3
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"], None
            else:
                return None, f"API Error: {response.status_code}"

        except Exception as e:
            return None, str(e)


# Create global instance
llm_service = LLMService()