"""OpenAI API client for text generation."""

import os
import logging
import time
from openai import AsyncOpenAI
from typing import Dict, Optional, List
from collections import Counter

# Configure logging
logger = logging.getLogger(__name__)
progress_logger = logging.getLogger('progress')
progress_logger.setLevel(logging.INFO)

class OpenAIClient:
    """Client for interacting with OpenAI API."""
    
    def __init__(self, api_key: str):
        """Initialize OpenAI client."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.error_counter = Counter()
        self.api_stats = Counter()
        self.recent_completions = []
        self.start_time = time.time()
        
    def _log_api_call(self, model: str, success: bool, error: Optional[str] = None):
        """Log API call statistics."""
        elapsed_time = time.time() - self.start_time
        
        if success:
            self.api_stats[f'{model}_success'] += 1
        else:
            self.api_stats[f'{model}_failure'] += 1
            if error:
                self.error_counter[error] += 1
                
        status = (
            f"API Stats (after {elapsed_time:.1f}s):\n"
            f"- Calls: {dict(self.api_stats)}\n"
            f"- Errors: {dict(self.error_counter)}"
        )
        progress_logger.info(status)
        
    def _log_completion(self, model: str, prompt_type: str, tokens: int, completion: str):
        """Log completion details."""
        sample = {
            'model': model,
            'type': prompt_type,
            'tokens': tokens,
            'preview': completion[:200] + "..." if len(completion) > 200 else completion
        }
        
        self.recent_completions.append(sample)
        if len(self.recent_completions) > 10:
            self.recent_completions.pop(0)
            
        progress_logger.info(
            f"\nRecent Completion ({model} - {prompt_type}):\n"
            f"- Preview: {sample['preview']}\n"
            f"- Tokens: {tokens}"
        )
        
    def get_model_config(self, model: str) -> Dict[str, int]:
        """Get configuration for specified model."""
        configs = {
            'gpt-4': {
                'context_window': 8192,
                'max_output_tokens': 4096,
            },
            'gpt-3.5-turbo': {
                'context_window': 4096,
                'max_output_tokens': 2048,
            },
            'gpt-4o-mini': {
                'context_window': 128000,
                'max_output_tokens': 16384,
            },
            'o1-preview': {
                'context_window': 128000,
                'max_output_tokens': 32768,
            },
            'o3-mini': {
                'context_window': 200000,
                'max_output_tokens': 100000,
            }
        }
        return configs.get(model, configs['gpt-3.5-turbo'])
        
    def create_initial_summary_prompt(self, filename: str, content: str, metrics: Dict[str, List[str]] = None) -> str:
        """Create prompt for initial summary generation."""
        metrics_context = ""
        if metrics:
            metrics_context = "\nKey metrics found in the document:\n"
            for metric, values in metrics.items():
                metrics_context += f"- {metric}: {', '.join(values)}\n"
        
        return f"""Analyze this financial document and create a clear, data-driven summary. Focus on the most important quantitative insights and market intelligence.

Your summary should naturally incorporate:
- Key financial metrics (revenue, earnings, margins, etc.)
- Important market movements and price changes
- Growth rates and forward-looking projections
- Relevant risk metrics and probabilities
- Comparative data and peer analysis

Write in a natural style while ensuring all critical numbers and metrics are preserved. Avoid rigid formatting - let the data flow naturally in your analysis.{metrics_context}

Document: {filename}

Content:
{content}

Remember: Focus on telling the quantitative story while preserving the precision of the original data."""

    def create_batch_summary_prompt(self, summaries: str, word_count: int) -> str:
        """Create prompt for consolidating batch summaries."""
        return f"""Synthesize these financial analyses into a cohesive narrative that preserves the key quantitative insights. Look for patterns and relationships between the data points while maintaining precision.

As you combine the analyses:
- Preserve important numerical data and metrics
- Highlight meaningful patterns and trends
- Connect related data points across summaries
- Maintain the context of market movements
- Keep significant risk metrics and probabilities

Source Summaries:
{summaries}

Target Length: {word_count} words

Remember: Focus on creating a clear, data-driven narrative that maintains the accuracy of the original metrics."""

    def create_final_summary_prompt(self, analyses: str) -> str:
        """Create prompt for final summary generation."""
        return f"""Create an executive-level synthesis of these financial analyses. Focus on delivering clear insights while preserving the precision of important data points.

Your summary should naturally incorporate:
- Critical financial metrics and performance data
- Key market movements and trends
- Important risk factors and probabilities
- Forward-looking projections and targets
- Comparative analysis and benchmarks

Write in a clear, executive style while ensuring that:
- Important numerical data is preserved
- Market insights are supported by data
- Risk assessments are quantified
- Projections include specific metrics
- Recommendations are data-driven

Source Analyses:
{analyses}

Remember: Focus on delivering actionable insights while maintaining the accuracy of the underlying data."""

    async def generate_summary(
        self,
        prompt: str,
        model: str = 'gpt-4',
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate summary using OpenAI API."""
        try:
            progress_logger.info(f"Generating summary with {model}")
            
            system_prompt = """You are an experienced financial analyst who excels at synthesizing complex financial information into clear, insightful narratives. Your analyses naturally weave together:

- Important financial metrics and data points
- Market movements and their implications
- Growth trends and future projections
- Risk factors and their potential impacts
- Comparative analysis and industry context

While you write in an engaging, natural style, you ensure that critical numerical data and metrics are preserved with precision. Your goal is to tell the quantitative story behind the data while maintaining complete accuracy."""

            # For o1-preview, include system prompt content in the user message
            if model == 'o1-preview':
                messages = [
                    {
                        "role": "user", 
                        "content": f"{system_prompt}\n\n{prompt}"
                    }
                ]
            else:
                messages = [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {"role": "user", "content": prompt}
                ]
            
            # Configure parameters based on model
            params = {
                "model": model,
                "messages": messages,
                "presence_penalty": 0.0,
                "frequency_penalty": 0.0
            }
            
            # Add temperature parameter only for models that support it
            if model not in ["o1-preview", "o3-mini"]:
                params["temperature"] = 0.3
            
            # Use correct token parameter based on model
            if model in ["o1-preview", "o3-mini"]:
                params["max_completion_tokens"] = max_tokens
            else:
                params["max_tokens"] = max_tokens
                
            response = await self.client.chat.completions.create(**params)
            
            completion = response.choices[0].message.content.strip()
            
            # Log successful completion
            self._log_api_call(model, True)
            self._log_completion(
                model,
                "Summary Generation",
                response.usage.total_tokens,
                completion
            )
            
            return completion
            
        except Exception as e:
            error_type = type(e).__name__
            self._log_api_call(model, False, error_type)
            logger.error(f"Error generating summary: {e}")
            return None
