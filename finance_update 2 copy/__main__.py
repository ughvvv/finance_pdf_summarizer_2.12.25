"""Main entry point for the financial report processor."""

import os
import sys
import logging
import asyncio
from config import Config
from report_pipeline import ReportPipeline
from clients.dropbox_client import DropboxClient
from clients.openai_client import OpenAIClient
from services.text_extractor import PDFTextExtractor
from services.summarizer_service import SummarizerService
from services.email_notifier import EmailNotifier
from services.chunk_manager import ChunkManager
from services.prompt_manager import PromptManager

from utils.log_handler import TokenSizeRotatingFileHandler

# Configure logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(log_format)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Add stdout handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
root_logger.addHandler(stream_handler)

# Add rotating file handler
file_handler = TokenSizeRotatingFileHandler(
    filename='finance_update.log',
    max_tokens=120000,  # 120k tokens limit
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

async def main():
    """Main asynchronous function to run the financial report processing."""
    try:
        logger.info("Starting Financial Report Processing")
        logger.info("Current working directory: %s", os.getcwd())
        
        # Initialize config
        logger.info("Initializing configuration")
        config = Config()
        
        # Initialize clients
        logger.info("Initializing clients")
        dropbox_client = DropboxClient(
            refresh_token=config.dropbox_refresh_token,
            app_key=config.dropbox_app_key,
            app_secret=config.dropbox_app_secret
        )
        openai_client = OpenAIClient(config.openai_key)
        
        # Initialize core services
        logger.info("Initializing core services")
        text_extractor = PDFTextExtractor()
        email_notifier = EmailNotifier(config)
        chunk_manager = ChunkManager(max_chunk_size=config.max_chunk_size)
        prompt_manager = PromptManager()
        
        # Initialize summarizer service
        summarizer_service = SummarizerService(
            openai_client=openai_client,
            chunk_manager=chunk_manager,
            prompt_manager=prompt_manager
        )
        
        # Create pipeline
        logger.info("Creating report pipeline")
        pipeline = ReportPipeline(
            config=config,
            dropbox_client=dropbox_client,
            pdf_processor=text_extractor,
            summarizer_service=summarizer_service,
            email_sender=email_notifier
        )
        
        # Run the pipeline
        logger.info("Starting report processing")
        final_analysis = await pipeline.run()
        
        if final_analysis:
            logger.info("Financial Report Processing Completed Successfully")
        else:
            logger.warning("Pipeline completed but no analysis was generated")
            
    except Exception as exc:
        logger.error("Error in main process: %s", exc, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
