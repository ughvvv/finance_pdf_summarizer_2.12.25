"""Service for handling parallel processing of reports with progress tracking."""

import logging
import asyncio
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager
import time

from utils.text_processor import TextProcessor
from services.validation_service import ValidationService
from services.summarizer_service import SummarizerService, SummaryConfig
from utils.exceptions import (
    ProcessingError,
    ValidationError,
    SummaryError,
    create_error_report,
    suggest_recovery_action
)

logger = logging.getLogger(__name__)

@dataclass
class BatchProgress:
    """Track progress of batch processing."""
    total: int
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of processed items."""
        processed = self.completed + self.failed
        return (self.completed / processed) * 100 if processed > 0 else 0
    
    def to_dict(self) -> Dict:
        """Convert progress to dictionary for reporting."""
        return {
            'total': self.total,
            'completed': self.completed,
            'failed': self.failed,
            'in_progress': self.in_progress,
            'success_rate': f"{self.success_rate:.1f}%",
            'remaining': self.total - (self.completed + self.failed)
        }

@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    max_concurrent: int = 15  # Increased from 5 to handle more parallel tasks
    retry_attempts: int = 2
    retry_delay: float = 1.0  # seconds
    progress_interval: float = 5.0  # seconds

class BatchProcessor:
    """Handles parallel processing of reports with progress tracking."""

    def __init__(
        self,
        validation_service: ValidationService,
        summarizer_service: SummarizerService,
        config: BatchConfig = BatchConfig()
    ):
        self.validation_service = validation_service
        self.summarizer_service = summarizer_service
        self.config = config
        self.progress = None
        self._progress_task = None
        self._stop_progress = False

    async def _report_progress(self):
        """Periodically report batch processing progress."""
        while not self._stop_progress and self.progress:
            progress_dict = self.progress.to_dict()
            logger.info(
                "Batch Progress: %d/%d completed (%s success rate), %d failed, %d remaining",
                progress_dict['completed'],
                progress_dict['total'],
                progress_dict['success_rate'],
                progress_dict['failed'],
                progress_dict['remaining']
            )
            await asyncio.sleep(self.config.progress_interval)

    @asynccontextmanager
    async def progress_tracking(self, total_items: int):
        """Context manager for tracking batch progress."""
        self.progress = BatchProgress(total=total_items)
        self._stop_progress = False
        self._progress_task = asyncio.create_task(self._report_progress())
        try:
            yield self.progress
        finally:
            self._stop_progress = True
            if self._progress_task:
                self._progress_task.cancel()
                try:
                    await self._progress_task
                except asyncio.CancelledError:
                    pass
            self._progress_task = None

    async def process_with_retry(
        self,
        item: Any,
        process_func: Callable,
        item_name: str,
        progress: BatchProgress
    ) -> Optional[Dict]:
        """Process an item with retry logic."""
        progress.in_progress += 1
        failed_attempts = []
        
        for attempt in range(self.config.retry_attempts):
            try:
                result = await process_func(item)
                if result:
                    progress.completed += 1
                    progress.in_progress -= 1
                    return result
                
                error = ProcessingError(
                    f"Processing {item_name} returned None on attempt {attempt + 1}",
                    processed_count=progress.completed,
                    failed_items=[item_name],
                    recovery_action="Retrying with delay"
                )
                failed_attempts.append(error)
                logger.warning(
                    "Processing attempt failed: %s",
                    create_error_report(error)
                )
                
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    
            except Exception as e:
                error = ProcessingError(
                    f"Error processing {item_name} on attempt {attempt + 1}: {str(e)}",
                    processed_count=progress.completed,
                    failed_items=[item_name],
                    recovery_action=suggest_recovery_action(e) if isinstance(e, (ValidationError, SummaryError)) else None
                )
                failed_attempts.append(error)
                logger.error(
                    "Processing error: %s",
                    create_error_report(error)
                )
                
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay)
        
        progress.failed += 1
        progress.in_progress -= 1
        
        # Raise final error with all attempt details
        raise ProcessingError(
            f"Failed to process {item_name} after {self.config.retry_attempts} attempts",
            processed_count=progress.completed,
            failed_items=[item_name],
            details={
                "failed_attempts": [
                    create_error_report(e) for e in failed_attempts
                ]
            }
        )

    async def process_reports(
        self,
        reports: List[Dict],
        summary_config: SummaryConfig
    ) -> List[Dict]:
        """
        Process a batch of reports in parallel with progress tracking.
        
        Args:
            reports: List of report dictionaries with 'text' and 'file_name'
            summary_config: Configuration for summarization
            
        Returns:
            List of processed reports with summaries
        """
        async def process_single_report(report: Dict) -> Optional[Dict]:
            """Process a single report with validation and summarization."""
            try:
                # Validate text
                if not self.validation_service.validate_extracted_text(report['text']):
                    raise ValidationError(
                        f"No valid text to process for {report['file_name']}",
                        text_preview=TextProcessor.format_preview(report['text'])
                    )

                logger.info(f"Processing summary for: {report['file_name']}")
                
                # Process the report text using summarizer service
                summary = await self.summarizer_service.process_report_text(
                    text=report['text'],
                    config=summary_config,
                    name=report['file_name']
                )

                if not summary:
                    raise SummaryError(
                        f"No successful summary generated for {report['file_name']}",
                        model=summary_config.model,
                        text_preview=TextProcessor.format_preview(report['text'])
                    )

                logger.info(f"Completed processing {report['file_name']}")
                return {
                    'file_name': report['file_name'],
                    'summary': summary
                }

            except Exception as e:
                logger.error(
                    f"Error processing report {report['file_name']}: {e}",
                    exc_info=True
                )
                raise

        async with self.progress_tracking(len(reports)) as progress:
            # Create processing tasks with semaphore for concurrency control
            semaphore = asyncio.Semaphore(self.config.max_concurrent)
            
            async def process_with_semaphore(report):
                async with semaphore:
                    return await self.process_with_retry(
                        report,
                        process_single_report,
                        report['file_name'],
                        progress
                    )
            
            # Process all reports concurrently with semaphore control
            results = []
            batch_tasks = [process_with_semaphore(report) for report in reports]
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            successful_results = [
                r for r in results
                if not isinstance(r, Exception) and r is not None
            ]
            
            # Log final results
            final_progress = progress.to_dict()
            if len(successful_results) < len(reports):
                error = ProcessingError(
                    "Some reports failed to process",
                    batch_size=len(reports),
                    processed_count=len(successful_results),
                    failed_items=[
                        r['file_name'] for r in reports
                        if r['file_name'] not in [s['file_name'] for s in successful_results]
                    ]
                )
                logger.error(
                    "Batch processing completed with errors: %s",
                    create_error_report(error)
                )
            else:
                logger.info(
                    "Batch processing completed successfully: %d/%d processed (%s success rate)",
                    final_progress['completed'],
                    final_progress['total'],
                    final_progress['success_rate']
                )
            
            return successful_results

    async def process_topics(
        self,
        topic_texts: Dict[str, str],
        summary_config: SummaryConfig
    ) -> Dict[str, str]:
        """
        Process topic summaries in parallel with progress tracking.
        
        Args:
            topic_texts: Dictionary of topic names to text content
            summary_config: Configuration for summarization
            
        Returns:
            Dictionary of topic names to processed summaries
        """
        async def process_single_topic(topic_data: tuple) -> Optional[tuple]:
            """Process a single topic's text."""
            topic, text = topic_data
            try:
                logger.info(f"Processing topic: {topic}")
                
                summary = await self.summarizer_service.process_report_text(
                    text=text,
                    config=summary_config,
                    name=f"Topic: {topic}"
                )

                if not summary:
                    raise SummaryError(
                        f"No successful summary generated for topic {topic}",
                        model=summary_config.model,
                        text_preview=TextProcessor.format_preview(text)
                    )

                logger.info(f"Completed processing topic {topic}")
                return (topic, summary)

            except Exception as e:
                logger.error(
                    f"Error processing topic {topic}: {e}",
                    exc_info=True
                )
                raise

        async with self.progress_tracking(len(topic_texts)) as progress:
            # Create processing tasks with semaphore
            semaphore = asyncio.Semaphore(self.config.max_concurrent)
            
            async def process_with_semaphore(topic_data):
                async with semaphore:
                    return await self.process_with_retry(
                        topic_data,
                        process_single_topic,
                        f"Topic: {topic_data[0]}",
                        progress
                    )
            
            # Process all topics concurrently with semaphore control
            results = []
            topic_items = list(topic_texts.items())
            batch_tasks = [process_with_semaphore((topic, text)) for topic, text in topic_items]
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            successful_results = [
                r for r in results
                if not isinstance(r, Exception) and r is not None
            ]
            
            # Log final results
            final_progress = progress.to_dict()
            if len(successful_results) < len(topic_texts):
                error = ProcessingError(
                    "Some topics failed to process",
                    batch_size=len(topic_texts),
                    processed_count=len(successful_results),
                    failed_items=[
                        topic for topic in topic_texts.keys()
                        if topic not in [t for t, _ in successful_results]
                    ]
                )
                logger.error(
                    "Topic processing completed with errors: %s",
                    create_error_report(error)
                )
            else:
                logger.info(
                    "Topic processing completed successfully: %d/%d processed (%s success rate)",
                    final_progress['completed'],
                    final_progress['total'],
                    final_progress['success_rate']
                )
            
            # Convert results back to dictionary
            return {topic: summary for topic, summary in successful_results}
