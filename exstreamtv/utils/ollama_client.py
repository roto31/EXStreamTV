"""Ollama AI client for log analysis, error troubleshooting, and conversational AI"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A message in a chat conversation."""
    
    role: str  # "system", "user", or "assistant"
    content: str
    
    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatConfig:
    """Configuration for chat generation."""
    
    temperature: float = 0.7  # Higher for more creative responses
    top_p: float = 0.9
    num_predict: int = 2000  # More tokens for conversational responses
    stop: list[str] = field(default_factory=list)
    
    def to_options(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "num_predict": self.num_predict,
            "stop": self.stop if self.stop else None,
        }


class OllamaClient:
    """Client for interacting with Ollama AI for log analysis, troubleshooting, and conversations"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:latest",
        chat_model: str | None = None,
        timeout: float = 120.0,
    ):
        """
        Initialize Ollama client

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434)
            model: Model to use for analysis (default: llama3.2:latest)
            chat_model: Optional separate model for chat (uses model if not specified)
            timeout: Request timeout in seconds (default: 120.0 for longer conversations)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.chat_model = chat_model or model
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"Initialized Ollama client with base_url={base_url}, model={model}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def is_available(self) -> bool:
        """Check if Ollama is available and responsive"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception as e:
            logger.exception(f"Error listing models: {e}")
            return []

    async def analyze_error(
        self,
        error_message: str,
        context: dict[str, Any] | None = None,
        log_excerpt: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze an error using Ollama AI

        Args:
            error_message: The error message to analyze
            context: Additional context (file, function, component, etc.)
            log_excerpt: Relevant log excerpt surrounding the error

        Returns:
            Dict with analysis results including:
            - root_cause: Identified root cause
            - severity: Error severity (critical, high, medium, low)
            - fix_suggestions: List of fix suggestions
            - confidence: AI confidence level (0-1)
        """
        try:
            # Build analysis prompt
            prompt = self._build_error_analysis_prompt(error_message, context, log_excerpt)

            # Query Ollama
            response = await self._generate(prompt)

            # Parse response
            analysis = self._parse_error_analysis(response)

            logger.info(f"Error analysis completed: {analysis.get('root_cause', 'Unknown')[:100]}")
            return analysis

        except Exception as e:
            logger.exception(f"Error during Ollama analysis: {e}")
            return {
                "root_cause": "Unknown - AI analysis failed",
                "severity": "medium",
                "fix_suggestions": [],
                "confidence": 0.0,
                "error": str(e),
            }

    async def suggest_fix(
        self,
        error_type: str,
        error_details: str,
        current_config: dict[str, Any] | None = None,
        code_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Get AI-powered fix suggestions for a specific error

        Args:
            error_type: Type of error (timeout, connection, ffmpeg, etc.)
            error_details: Detailed error information
            current_config: Current configuration values
            code_context: Relevant code snippet

        Returns:
            Dict with fix suggestions including:
            - fix_type: Type of fix (config, code, dependency, etc.)
            - changes: Specific changes to make
            - rationale: Why this fix should work
            - risks: Potential risks of applying the fix
        """
        try:
            prompt = self._build_fix_suggestion_prompt(
                error_type, error_details, current_config, code_context
            )

            response = await self._generate(prompt)
            fix = self._parse_fix_suggestion(response)

            logger.info(f"Fix suggestion generated: {fix.get('fix_type', 'unknown')}")
            return fix

        except Exception as e:
            logger.exception(f"Error generating fix suggestion: {e}")
            return {
                "fix_type": "unknown",
                "changes": [],
                "rationale": "AI fix generation failed",
                "risks": ["Unknown - manual intervention recommended"],
                "error": str(e),
            }

    async def analyze_log_pattern(
        self, log_lines: list[str], timeframe: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze log patterns to identify recurring issues

        Args:
            log_lines: List of log lines to analyze
            timeframe: Timeframe description (e.g., "last 1 hour")

        Returns:
            Dict with pattern analysis including:
            - patterns: List of identified patterns
            - trends: Identified trends
            - recommendations: Proactive recommendations
        """
        try:
            prompt = self._build_pattern_analysis_prompt(log_lines, timeframe)
            response = await self._generate(prompt)
            analysis = self._parse_pattern_analysis(response)

            logger.info(
                f"Pattern analysis completed: {len(analysis.get('patterns', []))} patterns found"
            )
            return analysis

        except Exception as e:
            logger.exception(f"Error analyzing log patterns: {e}")
            return {"patterns": [], "trends": [], "recommendations": [], "error": str(e)}

    async def _generate(self, prompt: str) -> str:
        """Generate response from Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more deterministic analysis
                    "top_p": 0.9,
                    "num_predict": 1000,  # Max tokens for response
                },
            }

            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return ""

        except Exception as e:
            logger.exception(f"Error calling Ollama API: {e}")
            raise

    def _build_error_analysis_prompt(
        self, error_message: str, context: dict[str, Any] | None, log_excerpt: str | None
    ) -> str:
        """Build prompt for error analysis"""
        prompt = f"""You are an expert system administrator analyzing errors in a video streaming server (StreamTV).

ERROR MESSAGE:
{error_message}
"""

        if context:
            prompt += "\nCONTEXT:\n"
            for key, value in context.items():
                prompt += f"- {key}: {value}\n"

        if log_excerpt:
            prompt += f"\nRELATED LOG EXCERPT:\n{log_excerpt}\n"

        prompt += """
Please analyze this error and provide:

1. ROOT CAUSE: What is the underlying cause of this error?
2. SEVERITY: Rate the severity (critical/high/medium/low)
3. FIX SUGGESTIONS: List 3-5 specific ways to fix this issue
4. CONFIDENCE: Your confidence level (0.0-1.0)

Format your response as JSON:
{
  "root_cause": "...",
  "severity": "...",
  "fix_suggestions": ["...", "..."],
  "confidence": 0.0
}
"""
        return prompt

    def _build_fix_suggestion_prompt(
        self,
        error_type: str,
        error_details: str,
        current_config: dict[str, Any] | None,
        code_context: str | None,
    ) -> str:
        """Build prompt for fix suggestions"""
        prompt = f"""You are an expert system administrator fixing errors in a video streaming server (StreamTV).

ERROR TYPE: {error_type}

ERROR DETAILS:
{error_details}
"""

        if current_config:
            prompt += f"\nCURRENT CONFIGURATION:\n{json.dumps(current_config, indent=2)}\n"

        if code_context:
            prompt += f"\nRELEVANT CODE:\n{code_context}\n"

        prompt += """
Please suggest a fix for this error. Provide:

1. FIX TYPE: config/code/dependency/restart/other
2. CHANGES: Specific changes to make (be precise)
3. RATIONALE: Why this fix should work
4. RISKS: Potential risks or side effects

Format your response as JSON:
{
  "fix_type": "...",
  "changes": [
    {"target": "...", "change": "...", "value": "..."}
  ],
  "rationale": "...",
  "risks": ["..."]
}
"""
        return prompt

    def _build_pattern_analysis_prompt(self, log_lines: list[str], timeframe: str | None) -> str:
        """Build prompt for pattern analysis"""
        log_sample = "\n".join(log_lines[:500])  # Limit to 500 lines

        prompt = f"""You are an expert system administrator analyzing log patterns in a video streaming server (StreamTV).

TIMEFRAME: {timeframe or "Recent logs"}

LOG SAMPLE ({len(log_lines)} lines):
{log_sample}

Please analyze these logs and identify:

1. PATTERNS: Recurring error patterns or issues
2. TRENDS: Are errors increasing, decreasing, or stable?
3. RECOMMENDATIONS: Proactive steps to prevent issues

Format your response as JSON:
{{
  "patterns": [
    {{"pattern": "...", "frequency": "...", "severity": "..."}}
  ],
  "trends": [
    {{"trend": "...", "description": "..."}}
  ],
  "recommendations": ["...", "..."]
}}
"""
        return prompt

    def _parse_error_analysis(self, response: str) -> dict[str, Any]:
        """Parse error analysis response"""
        try:
            # Try to extract JSON from response
            response = response.strip()

            # Find JSON block
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)

            # Fallback: parse manually
            return {
                "root_cause": response[:200],
                "severity": "medium",
                "fix_suggestions": [response[200:400]] if len(response) > 200 else [],
                "confidence": 0.5,
            }

        except Exception as e:
            logger.exception(f"Error parsing analysis response: {e}")
            return {
                "root_cause": response[:200] if response else "Unknown",
                "severity": "medium",
                "fix_suggestions": [],
                "confidence": 0.3,
            }

    def _parse_fix_suggestion(self, response: str) -> dict[str, Any]:
        """Parse fix suggestion response"""
        try:
            response = response.strip()
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)

            return {
                "fix_type": "manual",
                "changes": [{"target": "unknown", "change": response[:200], "value": ""}],
                "rationale": response[200:400] if len(response) > 200 else "See AI response",
                "risks": ["Manual review required"],
            }

        except Exception as e:
            logger.exception(f"Error parsing fix suggestion: {e}")
            return {
                "fix_type": "manual",
                "changes": [],
                "rationale": response[:200] if response else "Unknown",
                "risks": ["Parsing failed - manual intervention required"],
            }

    def _parse_pattern_analysis(self, response: str) -> dict[str, Any]:
        """Parse pattern analysis response"""
        try:
            response = response.strip()
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)

            return {
                "patterns": [],
                "trends": [],
                "recommendations": [response[:200]] if response else [],
            }

        except Exception as e:
            logger.exception(f"Error parsing pattern analysis: {e}")
            return {"patterns": [], "trends": [], "recommendations": []}

    # =========================================================================
    # Chat/Conversation API Methods
    # =========================================================================

    async def chat(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        config: ChatConfig | None = None,
    ) -> str:
        """
        Send a chat message and get a response.
        
        This is a simpler interface for conversational AI that handles
        system prompts and conversation history.
        
        Args:
            prompt: The user's message
            system_prompt: Optional system prompt to set context
            history: Optional conversation history [{"role": "user/assistant", "content": "..."}]
            config: Optional chat configuration
            
        Returns:
            The assistant's response text
        """
        try:
            messages = []
            
            # Add system prompt if provided
            if system_prompt:
                messages.append(ChatMessage(role="system", content=system_prompt))
            
            # Add conversation history
            if history:
                for msg in history:
                    messages.append(ChatMessage(
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                    ))
            
            # Add current user message
            messages.append(ChatMessage(role="user", content=prompt))
            
            # Generate response
            response = await self.chat_completion(messages, config)
            
            return response
            
        except Exception as e:
            logger.exception(f"Error in chat: {e}")
            return ""

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        config: ChatConfig | None = None,
    ) -> str:
        """
        Generate a chat completion from a list of messages.
        
        Uses Ollama's /api/chat endpoint for proper multi-turn conversations.
        
        Args:
            messages: List of ChatMessage objects
            config: Optional chat configuration
            
        Returns:
            The assistant's response text
        """
        try:
            config = config or ChatConfig()
            
            # Convert messages to dict format
            message_dicts = [msg.to_dict() for msg in messages]
            
            payload = {
                "model": self.chat_model,
                "messages": message_dicts,
                "stream": False,
                "options": config.to_options(),
            }
            
            logger.debug(f"Sending chat request with {len(messages)} messages")
            
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            
            if response.status_code == 200:
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "")
                
                logger.debug(f"Received chat response: {len(content)} chars")
                return content
            else:
                logger.error(f"Ollama chat API error: {response.status_code} - {response.text}")
                return ""
                
        except Exception as e:
            logger.exception(f"Error in chat completion: {e}")
            raise

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        config: ChatConfig | None = None,
    ):
        """
        Generate a streaming chat completion.
        
        Yields response chunks as they arrive.
        
        Args:
            messages: List of ChatMessage objects
            config: Optional chat configuration
            
        Yields:
            Response text chunks
        """
        try:
            config = config or ChatConfig()
            
            message_dicts = [msg.to_dict() for msg in messages]
            
            payload = {
                "model": self.chat_model,
                "messages": message_dicts,
                "stream": True,
                "options": config.to_options(),
            }
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            message = data.get("message", {})
                            content = message.get("content", "")
                            if content:
                                yield content
                            
                            # Check if done
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.exception(f"Error in streaming chat: {e}")
            raise

    async def generate_with_context(
        self,
        prompt: str,
        context: str | None = None,
        system_prompt: str | None = None,
        config: ChatConfig | None = None,
    ) -> str:
        """
        Generate a response with optional context injection.
        
        Useful for RAG-style queries where you want to include
        retrieved context in the prompt.
        
        Args:
            prompt: The user's query
            context: Optional context to include (e.g., retrieved documents)
            system_prompt: Optional system prompt
            config: Optional generation config
            
        Returns:
            The generated response
        """
        # Build full prompt with context
        full_prompt_parts = []
        
        if system_prompt:
            full_prompt_parts.append(system_prompt)
        
        if context:
            full_prompt_parts.append(f"\nCONTEXT:\n{context}\n")
        
        full_prompt_parts.append(f"\nQUERY: {prompt}")
        
        full_prompt = "\n".join(full_prompt_parts)
        
        # Use generate API for single-turn with context
        config = config or ChatConfig()
        
        try:
            payload = {
                "model": self.chat_model,
                "prompt": full_prompt,
                "stream": False,
                "options": config.to_options(),
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                logger.error(f"Ollama generate API error: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.exception(f"Error in generate with context: {e}")
            return ""

    async def embed(self, text: str) -> list[float]:
        """
        Generate embeddings for text.
        
        Useful for semantic search and similarity comparisons.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        try:
            payload = {
                "model": self.model,
                "prompt": text,
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
            else:
                logger.error(f"Ollama embeddings API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.exception(f"Error generating embeddings: {e}")
            return []

    async def get_model_info(self, model: str | None = None) -> dict[str, Any]:
        """
        Get information about a model.
        
        Args:
            model: Model name (uses default if not specified)
            
        Returns:
            Model information dict
        """
        try:
            model_name = model or self.model
            
            response = await self.client.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to get model info: {response.status_code}"}
                
        except Exception as e:
            logger.exception(f"Error getting model info: {e}")
            return {"error": str(e)}
