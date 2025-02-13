"""Service for handling text summarization with optimized token management."""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math

from clients.openai_client import OpenAIClient
from utils.text_processor import get_token_count, TextProcessor
from services.chunk_manager import ChunkManager
from services.prompt_manager import PromptManager
from utils.exceptions import (
    SummaryError,
    ChunkError,
    PromptError,
    create_error_report,
    suggest_recovery_action
)

logger = logging.getLogger(__name__)

@dataclass
class SummaryConfig:
    """Configuration for summarization parameters."""
    model: str
    context_window: int
    max_output_tokens: int
    min_output_tokens: int
    chunk_ratio: float = 0.8  # Default to using 80% of context window
    density_ratio: float = 0.9  # Default to using 90% of max tokens

class SummarizerService:
    """Handles text summarization with optimized token management."""

    def __init__(
        self,
        openai_client: OpenAIClient,
        chunk_manager: ChunkManager,
        prompt_manager: PromptManager
    ):
        self.openai_client = openai_client
        self.chunk_manager = chunk_manager
        self.prompt_manager = prompt_manager
        
        # Model configurations
        self.MODEL_CONFIGS = {
            'gpt-4o-mini': {
                'context_window': 8192,
                'max_output_tokens': 4000,
                'supports_temperature': True
            },
            'o1-preview': {
                'context_window': 128000,
                'max_output_tokens': 32768,
                'supports_temperature': False  # No temperature for o1 model
            },
            'o3-mini': {
                'context_window': 200000,
                'max_output_tokens': 100000,
                'supports_temperature': False
            }
        }
        
        # Target tokens for recursive summarization; this will be overridden dynamically for final model
        self.TARGET_TOKENS = 120000
        self.MIN_TOKENS_PER_SUMMARY = 1000
        self.MAX_TOKENS_PER_SUMMARY = 8000

    def _save_summaries(self, stage: str, summary_text: str) -> None:
        """
        Save combined summaries to a TXT file in the memlog folder.
        The file is named with a timestamp for tracking progression.
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"memlog/{stage}_summaries_{timestamp}.txt"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(summary_text)
        
        # Also save to a "latest" file for easy access
        latest_filepath = f"memlog/{stage}_summaries_latest.txt"
        with open(latest_filepath, "w", encoding="utf-8") as f:
            f.write(summary_text)

    async def generate_initial_summaries(
        self,
        pdf_texts: List[str],
        max_tokens: int = 4000,
        model: str = "gpt-4o-mini"
    ) -> List[str]:
        """Generate initial summaries for each PDF using gpt-4o-mini."""
        logger.info(f"Generating initial summaries for {len(pdf_texts)} PDFs")
        initial_summaries = []
        
        config = SummaryConfig(
            model=model,
            context_window=self.MODEL_CONFIGS[model]['context_window'],
            max_output_tokens=max_tokens,
            min_output_tokens=self.MIN_TOKENS_PER_SUMMARY
        )
        
        for i, text in enumerate(pdf_texts):
            try:
                summary = await self.process_report_text(
                    text=str(text),  # Ensure text is a string
                    config=config,
                    name=f"PDF {i+1}",
                    enable_variants=True
                )
                
                if summary:
                    initial_summaries.append(summary)
                    logger.info(f"Generated initial summary {i+1}/{len(pdf_texts)}")
                
            except Exception as e:
                logger.error(f"Error generating initial summary for PDF {i+1}: {e}")
                continue
        
        return initial_summaries

    async def recursive_group_summarize(
        self,
        summaries: List[str],
        target_tokens: int = 180000,  # Default target of 180k tokens
        model: str = "gpt-4o-mini",
        final_model: str = "o3-mini"
    ) -> str:
        """Recursively combine summaries only if total tokens exceed 180k.
        When summarization is needed, target getting as close to 180k as possible.
        """
        total_tokens = sum(get_token_count(s, model) for s in summaries)
        logger.info(f"Current total tokens: {total_tokens}, Target: {target_tokens}")
        
        # If under 180k tokens, no need for recursive summarization
        if total_tokens <= target_tokens:
            return "\n\n===\n\n".join(summaries)
        
        # Calculate how many groups we need to get close to 180k tokens
        # We want each summary to be around 6k tokens (180k / 30) to get a good distribution
        target_tokens_per_summary = 6000
        group_count = max(2, math.ceil(total_tokens / (target_tokens_per_summary * 30)))
        
        # Calculate max tokens per summary to stay close to 180k total
        max_tokens_per_summary = min(
            self.MAX_TOKENS_PER_SUMMARY,
            max(
                self.MIN_TOKENS_PER_SUMMARY,
                int((target_tokens / group_count) * 0.9)  # Use 90% to account for some variance
            )
        )
        
        logger.info(
            f"Forming {group_count} groups with max {max_tokens_per_summary} tokens each"
        )
        
        # Split into groups and summarize
        new_summaries = []
        chunk_size = max(1, len(summaries) // group_count)
        
        for i in range(0, len(summaries), chunk_size):
            group = summaries[i:i + chunk_size]
            combined_text = "\n\n---\n\n".join(group)
            
            try:
                prompt = self.prompt_manager.format_prompt(
                    name="group_summary",
                    variables={"text": str(combined_text)}
                )
                
                group_summary = await self.openai_client.generate_summary(
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens_per_summary
                )
                
                if group_summary:
                    new_summaries.append(group_summary)
                    logger.info(
                        f"Generated group summary {len(new_summaries)}/{group_count}"
                    )
                    
            except Exception as e:
                logger.error(f"Error in group summarization: {e}")
                continue
        
        if not new_summaries:
            raise SummaryError(
                "Failed to generate any group summaries",
                model=model,
                group_count=group_count
            )
        
        # Recursive call with new summaries
        return await self.recursive_group_summarize(
            new_summaries,
            target_tokens,
            model,
            final_model
        )

    async def generate_final_analysis(
        self,
        combined_summary: str,
        max_tokens: int = None,
        model: str = "o3-mini"
    ) -> str:
        """Generate final analysis using o3-mini model by default."""
        try:
            if max_tokens is None:
                max_tokens = self.MODEL_CONFIGS[model]['max_output_tokens']
            prompt = self.prompt_manager.format_prompt(
                name="final_analysis",
                variables={"text": str(combined_summary)},
                max_tokens=max_tokens
            )
            final_summary = await self.openai_client.generate_summary(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens
            )
            
            if not final_summary:
                raise SummaryError(
                    "Failed to generate final analysis",
                    model=model,
                    text_preview=TextProcessor.format_preview(combined_summary)
                )
            
            return final_summary
            
        except Exception as e:
            error = SummaryError(
                f"Failed to generate final analysis: {str(e)}",
                model=model,
                text_preview=TextProcessor.format_preview(combined_summary)
            )
            logger.error(f"Final analysis error: {create_error_report(error)}")
            raise error

    async def process_multiple_pdfs(
        self,
        pdf_texts: List[str],
        initial_max_tokens: int = 4000,
        final_max_tokens: int = None
    ) -> str:
        """Process multiple PDFs through the three-stage pipeline."""
        try:
            # Stage 1: Initial Summaries
            initial_summaries = await self.generate_initial_summaries(
                pdf_texts,
                max_tokens=initial_max_tokens
            )
            
            if not initial_summaries:
                raise SummaryError(
                    "No initial summaries generated",
                    pdf_count=len(pdf_texts)
                )
            # Save initial summaries
            combined_initial = "\n\n---\n\n".join(initial_summaries)
            self._save_summaries("initial", combined_initial)
            
            # Stage 2: Recursive Summarization (only if total tokens > 180k)
            combined_summary = await self.recursive_group_summarize(
                initial_summaries,
                target_tokens=180000,  # Fixed target of 180k tokens
                model="gpt-4o-mini",  # Use gpt-4o-mini for intermediate summarization
                final_model="o3-mini"
            )
            # Save recursive summaries
            self._save_summaries("recursive", combined_summary)
            
            # Stage 3: Final Analysis using o3-mini
            try:
                final_analysis = await self.generate_final_analysis(
                    combined_summary,
                    max_tokens=final_max_tokens,
                    model="o3-mini"
                )
                
                # Save final analysis even if later stages fail
                if final_analysis:
                    self._save_summaries("final", final_analysis)
                    logger.info("Saved final analysis to memlog/final_summaries.txt")
                
                return final_analysis
                
            except Exception as e:
                # If we have a partial final analysis, save it before re-raising
                if 'final_analysis' in locals() and final_analysis:
                    self._save_summaries("final_partial", final_analysis)
                    logger.info("Saved partial final analysis to memlog/final_partial_summaries.txt")
                raise
            
        except Exception as e:
            error = SummaryError(
                f"Failed to process multiple PDFs: {str(e)}",
                pdf_count=len(pdf_texts)
            )
            logger.error(f"Pipeline error: {create_error_report(error)}")
            raise error

    async def summarize_batch(
        self,
        batch_text: str,
        model: str,
        max_tokens: int,
        enable_variants: bool = True
    ) -> Tuple[str, Optional[str]]:
        """
        Summarize a batch of text while preserving key information.
        
        Args:
            batch_text: Text to summarize
            model: Model to use for summarization
            max_tokens: Maximum tokens for output
            enable_variants: Whether to enable A/B testing variants
            
        Returns:
            Tuple of (summary text, variant ID if used)
        """
        try:
            prompt = self.prompt_manager.format_prompt(
                name="initial_summary",
                variables={"text": str(batch_text)},
                enable_variants=enable_variants,
                max_tokens=max_tokens
            )
            
            template = self.prompt_manager.get_template(
                "initial_summary",
                enable_variants=enable_variants
            )
            variant_id = getattr(template, 'variant_id', None)
            
            summary = await self.openai_client.generate_summary(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens
            )
            
            if variant_id:
                success = bool(summary and len(summary.strip()) > 0)
                self.prompt_manager.record_variant_result(
                    "initial_summary",
                    variant_id,
                    success
                )
            
            if not summary or not summary.strip():
                raise SummaryError(
                    "Generated summary is empty",
                    model=model,
                    token_count=get_token_count(batch_text),
                    recovery_action="Try adjusting the max_tokens parameter or using a different model"
                )
            
            return summary, variant_id
            
        except Exception as e:
            error = SummaryError(
                f"Failed to generate summary: {str(e)}",
                model=model,
                token_count=get_token_count(batch_text),
                max_tokens=max_tokens,
                text_preview=TextProcessor.format_preview(batch_text)
            )
            logger.error("Summarization error: %s", create_error_report(error))
            raise error

    async def consolidate_chunks(
        self,
        chunks: List[str],
        model: str,
        max_tokens: int,
        enable_variants: bool = True
    ) -> Tuple[str, Optional[str]]:
        """
        Consolidate multiple chunks into a coherent summary.
        
        Args:
            chunks: List of text chunks to consolidate
            model: Model to use for consolidation
            max_tokens: Maximum tokens for output
            enable_variants: Whether to enable A/B testing variants
            
        Returns:
            Tuple of (consolidated text, variant ID if used)
        """
        try:
            combined_text = "\n\n---\n\n".join(chunks)
            
            prompt = self.prompt_manager.format_prompt(
                name="consolidate_chunks",
                variables={"text": str(combined_text)},
                enable_variants=enable_variants,
                max_tokens=max_tokens
            )
            
            template = self.prompt_manager.get_template(
                "consolidate_chunks",
                enable_variants=enable_variants
            )
            variant_id = getattr(template, 'variant_id', None)
            
            consolidated = await self.openai_client.generate_summary(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens
            )
            
            if variant_id:
                success = bool(consolidated and len(consolidated.strip()) > 0)
                self.prompt_manager.record_variant_result(
                    "consolidate_chunks",
                    variant_id,
                    success
                )
            
            if not consolidated or not consolidated.strip():
                raise SummaryError(
                    "Generated consolidated summary is empty",
                    model=model,
                    token_count=get_token_count(combined_text),
                    recovery_action="Try adjusting consolidation parameters"
                )
            
            return consolidated, variant_id
            
        except Exception as e:
            error = SummaryError(
                f"Failed to consolidate chunks: {str(e)}",
                model=model,
                chunk_count=len(chunks),
                total_tokens=get_token_count("\n\n".join(chunks))
            )
            logger.error("Chunk consolidation error: %s", create_error_report(error))
            raise error

    async def process_report_text(
        self,
        text: str,
        config: SummaryConfig,
        name: str = "report",
        enable_variants: bool = True
    ) -> Optional[str]:
        """
        Process a single report's text into a summary.
        
        Args:
            text: Report text to process
            config: Configuration for summarization
            name: Name of the report for logging
            enable_variants: Whether to enable A/B testing variants
            
        Returns:
            Summarized text if successful, None otherwise
        """
        try:
            text_chunks = self.chunk_manager.chunk_text(
                text,
                preserve_context=True,
                max_tokens=int(config.context_window * config.chunk_ratio)
            )
            
            chunk_summaries = []
            for i, chunk in enumerate(text_chunks):
                try:
                    chunk_prompt = self.prompt_manager.format_prompt(
                        name="initial_summary",
                        variables={
                            "text": str(chunk),
                            "part": f"{name} (Part {i+1}/{len(text_chunks)})"
                        },
                        enable_variants=enable_variants,
                        max_tokens=int(config.max_output_tokens * config.density_ratio)
                    )
                except Exception as e:
                    raise PromptError(
                        f"Failed to format prompt: {str(e)}",
                        template_name="initial_summary",
                        text_preview=TextProcessor.format_preview(chunk)
                    )
                
                template = self.prompt_manager.get_template(
                    "initial_summary",
                    enable_variants=enable_variants
                )
                variant_id = getattr(template, 'variant_id', None)
                
                chunk_summary = await self.openai_client.generate_summary(
                    prompt=chunk_prompt,
                    model=config.model,
                    max_tokens=int(config.max_output_tokens * config.density_ratio)
                )
                
                if variant_id:
                    success = bool(chunk_summary and len(chunk_summary.strip()) > 0)
                    self.prompt_manager.record_variant_result(
                        "initial_summary",
                        variant_id,
                        success
                    )
                
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
                    logger.info(f"Processed chunk {i+1}/{len(text_chunks)} of {name}")
            
            if len(chunk_summaries) > 1:
                try:
                    consolidation_prompt = self.prompt_manager.format_prompt(
                        name="group_summary",
                        variables={"text": str("\n\n---\n\n".join(chunk_summaries))},
                        enable_variants=enable_variants,
                        max_tokens=int(config.max_output_tokens)
                    )
                    
                    final_summary = await self.openai_client.generate_summary(
                        prompt=consolidation_prompt,
                        model=config.model,
                        max_tokens=int(config.max_output_tokens)
                    )
                    
                    return final_summary
                except Exception as e:
                    raise PromptError(
                        f"Failed to consolidate chunks: {str(e)}",
                        template_name="group_summary",
                        text_preview=TextProcessor.format_preview("\n".join(chunk_summaries))
                    )
            elif chunk_summaries:
                return chunk_summaries[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing report {name}: {str(e)}", exc_info=True)
            return None
