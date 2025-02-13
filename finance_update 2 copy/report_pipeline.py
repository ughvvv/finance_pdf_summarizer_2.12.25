"""Main pipeline for processing financial reports."""

import logging
import asyncio
from typing import List, Dict, Optional, Tuple
import io
from collections import defaultdict
from contextlib import contextmanager
import time
import re
from datetime import datetime

from config import Config
from clients.dropbox_client import DropboxClient
from clients.openai_client import OpenAIClient
from utils.pdf_processor import PDFProcessor
from utils.email_handler import EmailSender
from utils.text_processor import TextProcessor, get_token_count
from utils.exceptions import ProcessingError
from services.validation_service import ValidationService
from services.metrics_extractor import MetricsExtractor
from services.chunk_manager import ChunkManager
from services.summarizer_service import SummarizerService, SummaryConfig
from services.batch_processor import BatchProcessor, BatchConfig
from services.prompt_manager import PromptManager
from services.analysis_store import AnalysisStore
from services.email_notifier import EmailNotifier

logger = logging.getLogger(__name__)
progress_logger = logging.getLogger('progress')

@contextmanager
def timing_context(name: str):
    start_time = time.time()
    yield
    duration = time.time() - start_time
    logger.info("%s completed in %.2f seconds", name, duration)

class ReportPipeline:
    """Main class for report processing pipeline."""

    def __init__(
        self,
        config: Config,
        dropbox_client: DropboxClient,
        pdf_processor: PDFProcessor,
        summarizer_service: SummarizerService,
        email_sender: EmailSender
    ):
        """Initialize pipeline with required services."""
        self.config = config
        self.dropbox_client = dropbox_client
        self.pdf_processor = pdf_processor
        self.summarizer_service = summarizer_service
        self.email_sender = email_sender
        self.email_notifier = EmailNotifier(EmailSender(config))
        self.analysis_store = AnalysisStore()
        self.start_time = time.time()  # Initialize start_time
        
        # Initialize clients
        self.openai_client = OpenAIClient(config.openai_key)
        
        # Initialize core services
        self.validation_service = ValidationService()
        self.metrics_extractor = MetricsExtractor()
        # Initialize ChunkManager with standard GPT-4 parameters
        self.chunk_manager = ChunkManager(max_chunk_size=8000)  # Match context window of gpt-4o-mini
        self.prompt_manager = PromptManager()
        self.batch_processor = BatchProcessor(
            validation_service=self.validation_service,
            summarizer_service=self.summarizer_service,
            config=BatchConfig(
                max_concurrent=2,  # Reduced from 5 to 2 for more sequential processing
                retry_attempts=2,
                progress_interval=5.0
            )
        )

    async def run(self):
        """Run the full report processing pipeline."""
        try:
            logger.info("Starting report processing")
            
            # Get PDF files from Dropbox
            pdf_files = await self.dropbox_client.fetch_reports(self.config)
            if not pdf_files:
                logger.warning("No PDF files found")
                return
            
            print(f"\nFound {len(pdf_files)} PDF files\n")
            
            # Extract text from PDFs concurrently
            extraction_tasks = []
            for pdf_file in pdf_files:
                task = asyncio.create_task(self.pdf_processor.extract(pdf_file))
                extraction_tasks.append(task)
            
            # Wait for all extractions to complete
            extraction_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
            
            # Process results and handle any errors
            pdf_texts = []
            successful_files = []
            failed_files = []
            
            for i, result in enumerate(extraction_results):
                file_name = pdf_files[i].get('name', f'File {i}')
                
                if isinstance(result, Exception):
                    logger.error(f"Failed to process {file_name}: {str(result)}")
                    print(f"❌ Failed to process {file_name}")
                    failed_files.append(file_name)
                    continue
                    
                if result and isinstance(result, dict):
                    if result.get('error'):
                        logger.error(f"Error processing {file_name}: {result['error']}")
                        print(f"❌ Failed to process {file_name}")
                        failed_files.append(file_name)
                        continue
                        
                    if result.get('text'):
                        pdf_texts.append(result['text'])
                        successful_files.append(file_name)
                        logger.info(f"Successfully extracted text from {file_name}")
                        logger.info(f"Preview: {result['preview']}")
                        print(f"✅ Successfully processed {file_name}")
                    else:
                        logger.error(f"No text extracted from {file_name}")
                        print(f"❌ Failed to process {file_name}")
                        failed_files.append(file_name)
                else:
                    logger.error(f"Invalid extraction result for {file_name}")
                    print(f"❌ Failed to process {file_name}")
                    failed_files.append(file_name)
            
            # Log summary
            print(f"\nProcessing Summary:")
            print(f"- Successfully processed: {len(successful_files)} files")
            print(f"- Failed to process: {len(failed_files)} files")
            
            if failed_files:
                print("\nFailed files:")
                for file in failed_files:
                    print(f"- {file}")
            
            if not pdf_texts:
                logger.error("No text extracted from PDFs")
                return None
                
            # Process extracted texts through the pipeline
            with timing_context("Full Report Processing"):
                # Stage 1: Generate initial summaries for each PDF
                initial_summaries = await self.summarizer_service.generate_initial_summaries(
                    pdf_texts,
                    max_tokens=4000,
                    model="gpt-4o-mini"
                )
                
                if not initial_summaries:
                    logger.error("No initial summaries generated")
                    return None
                # Save combined initial summaries as a separate file in the memlog folder
                import os
                os.makedirs("memlog", exist_ok=True)
                combined_initial = "\n".join(initial_summaries)
                file_path = "memlog/combined_initial_summaries.md"
                with open(file_path, "w") as f:
                    f.write(combined_initial)
                    f.flush()
                logger.info(f"Combined initial summaries saved to {file_path}")
                
                
                # Stage 2: Recursively combine summaries until under target token count
                combined_summary = await self.summarizer_service.recursive_group_summarize(
                    initial_summaries,
                    target_tokens=self.summarizer_service.TARGET_TOKENS,
                    model="gpt-4o-mini"
                )
                
                if not combined_summary:
                    logger.error("Failed to generate combined summary")
                    return None
                
                # Stage 3: Generate final analysis using o1 model
                final_analysis = await self.summarizer_service.generate_final_analysis(
                    combined_summary,
                    max_tokens=20000
                )
                
                if final_analysis:
                    print("\n✅ Successfully generated final analysis\n")
                    print("Preview of final analysis:")
                    print(f"{final_analysis[:100]}...\n")
                    
                    # Store the analysis
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    analysis_path = f"analysis_archive/{datetime.now().year:04d}/{datetime.now().month:02d}-{datetime.now().strftime('%B')}/{datetime.now().day:02d}"
                    filename = f"analysis_{timestamp}.json"
                    
                    # Create analysis object with metadata
                    analysis_data = {
                        "timestamp": datetime.now().isoformat(),
                        "source_files": successful_files,
                        "failed_files": failed_files,
                        "analysis": {
                            "raw_text": final_analysis,
                            "sections": {
                                "market_overview": self.extract_section(final_analysis, "MARKET OVERVIEW"),
                                "regional_metrics": self.extract_section(final_analysis, "REGIONAL/SECTOR METRICS"),
                                "opportunities": {
                                    "mainstream": self.extract_section(final_analysis, "Mainstream Picks"),
                                    "contrarian": self.extract_section(final_analysis, "Contrarian Ideas")
                                },
                                "significance": self.extract_section(final_analysis, "MARKET SIGNIFICANCE"),
                                "recommendations": self.extract_section(final_analysis, "ACTIONABLE RECOMMENDATIONS"),
                                "conclusion": self.extract_section(final_analysis, "CONCLUSION")
                            }
                        }
                    }
                    
                    self.analysis_store.store_analysis(
                        analysis_data
                    )
                    
                    print(f"💾 Analysis stored at: {analysis_path}/{filename}\n")
                    
                    # Send email notification
                    await self.email_notifier.send_analysis(final_analysis)
                    
                else:
                    logger.error("Failed to generate final analysis")
                    
            return None
                
        except Exception as e:
            logger.error("Error in report processing pipeline: %s", e, exc_info=True)
            return None

    def extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from the analysis text."""
        pattern = f"{section_name}:?\\s*(.*?)(?=\n\n[A-Z][A-Z\\s]+:|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    async def process_and_send(self):
        """Process reports and send email."""
        try:
            print("\n🚀 Starting report processing pipeline...")
            final_analysis = await self.run()

            if not isinstance(final_analysis, str):
                logger.error(f"Invalid final_analysis type: {type(final_analysis)}")
                return

            if final_analysis:
                error_messages = [
                    "No PDFs to process",
                    "No valid text to process",
                    "Error:"
                ]

                if not any(msg in final_analysis for msg in error_messages):
                    print("\n✅ Pipeline completed successfully")
                else:
                    print(f"\n❌ Error: {final_analysis}")
                    logger.error(f"Pipeline failed: {final_analysis}")
            else:
                print("\n❌ Error: Final analysis was not generated")
                logger.error("Final analysis was not generated")

        except Exception as e:
            print(f"\n❌ Error in process_and_send: {str(e)}")
            logger.error("Error in process_and_send: %s", e, exc_info=True)
            raise
