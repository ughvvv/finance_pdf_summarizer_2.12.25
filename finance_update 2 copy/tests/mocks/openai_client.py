"""Mock implementation of OpenAI client for testing."""

from typing import Dict, Any, Optional
import json
import os
from pathlib import Path

class MockOpenAIClient:
    """Mock OpenAI client that returns predefined responses."""

    def __init__(self, responses_path: Optional[str] = None):
        """
        Initialize mock client with optional custom responses.
        
        Args:
            responses_path: Optional path to JSON file with custom responses
        """
        self.responses = {
            'gpt-4o': {
                'context_window': 16000,
                'max_output_tokens': 8000,
                'min_output_tokens': 1000
            },
            'gpt-4o-mini': {
                'context_window': 8000,
                'max_output_tokens': 4000,
                'min_output_tokens': 500
            },
            'o1-preview': {
                'context_window': 32000,
                'max_output_tokens': 16000,
                'min_output_tokens': 2000
            }
        }
        
        self.summary_responses = {
            'initial_summary': {
                'success': 'This is a mock initial summary that preserves key information.',
                'empty': '',
                'error': None
            },
            'consolidate_chunks': {
                'success': 'This is a mock consolidated summary combining multiple chunks.',
                'empty': '',
                'error': None
            },
            'final_analysis': {
                'success': 'This is a mock final analysis with a professional tone.',
                'empty': '',
                'error': None
            }
        }
        
        if responses_path:
            self._load_custom_responses(responses_path)
        
        self.call_history = []

    def _load_custom_responses(self, path: str):
        """Load custom responses from JSON file."""
        try:
            with open(path, 'r') as f:
                custom_responses = json.load(f)
            self.responses.update(custom_responses.get('models', {}))
            self.summary_responses.update(custom_responses.get('summaries', {}))
        except Exception as e:
            raise ValueError(f"Failed to load custom responses from {path}: {e}")

    def get_model_config(self, model: str) -> Dict[str, int]:
        """Get model configuration."""
        if model not in self.responses:
            raise ValueError(f"Unknown model: {model}")
        return self.responses[model]

    def create_initial_summary_prompt(self, name: str, text: str) -> str:
        """Create prompt for initial summary."""
        return f"Mock prompt for {name}: {text[:100]}..."

    def create_final_summary_prompt(self, text: str) -> str:
        """Create prompt for final summary."""
        return f"Mock final prompt: {text[:100]}..."

    async def generate_summary(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        response_type: str = 'success'
    ) -> Optional[str]:
        """
        Generate mock summary based on prompt and model.
        
        Args:
            prompt: Input prompt
            model: Model to use
            max_tokens: Maximum tokens for output
            response_type: Type of response to return ('success', 'empty', 'error')
            
        Returns:
            Mock summary text or None for error case
        """
        self.call_history.append({
            'prompt': prompt,
            'model': model,
            'max_tokens': max_tokens,
            'response_type': response_type
        })
        
        # Determine response type based on prompt content
        response_key = 'initial_summary'
        if 'combining these summaries' in prompt:
            response_key = 'consolidate_chunks'
        elif 'final analysis' in prompt:
            response_key = 'final_analysis'
        
        return self.summary_responses[response_key][response_type]

    def get_call_history(self) -> list:
        """Get history of mock client calls."""
        return self.call_history

    def clear_call_history(self):
        """Clear history of mock client calls."""
        self.call_history = []

    def set_response(
        self,
        response_key: str,
        response_type: str,
        response: Optional[str]
    ):
        """
        Set custom response for testing.
        
        Args:
            response_key: Key for response type ('initial_summary', etc.)
            response_type: Type of response ('success', 'empty', 'error')
            response: Response text or None
        """
        if response_key not in self.summary_responses:
            raise ValueError(f"Invalid response key: {response_key}")
        if response_type not in ['success', 'empty', 'error']:
            raise ValueError(f"Invalid response type: {response_type}")
        self.summary_responses[response_key][response_type] = response
