"""Test script for the financial summary pipeline."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
import sys
import os
import json
import pytest
import io

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from clients.dropbox_client import DropboxClient
from services.pdf_fetcher import PDFFetcher
from utils.pdf_processor import PDFProcessor
from utils.structured_extractor import StructuredExtractor
from utils.executive_summary import ExecutiveSummaryGenerator, ExecutiveSummaryConfig
from utils.email_handler import EmailHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'  # Simplified format
)
logger = logging.getLogger(__name__)

# Reduce verbosity of other loggers
logging.getLogger('pdfminer').setLevel(logging.ERROR)
logging.getLogger('dropbox').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

def convert_to_dict(obj):
    """Convert dataclass objects to dictionaries."""
    if isinstance(obj, (list, tuple)):
        return [convert_to_dict(item) for item in obj]
    elif hasattr(obj, '__dataclass_fields__'):  # Check if it's a dataclass
        return {field: convert_to_dict(getattr(obj, field)) for field in obj.__dataclass_fields__}
    else:
        return obj

@pytest.mark.asyncio
async def test_pipeline():
    """Test the financial summary pipeline with a limited number of PDFs."""
    try:
        # Initialize configuration
        config = Config.create()
        logger.info("Configuration initialized successfully")
        
        # Initialize clients
        dropbox_client = DropboxClient(
            refresh_token=config.dropbox_refresh_token,
            app_key=config.dropbox_app_key,
            app_secret=config.dropbox_app_secret
        )
        pdf_fetcher = PDFFetcher(dropbox_client)
        
        # Fetch PDFs
        logger.info("Fetching PDFs from Dropbox...")
        pdf_files = await pdf_fetcher.fetch_pdfs(config)
        logger.info(f"Found {len(pdf_files)} PDF files in Dropbox")
        
        if not pdf_files:
            logger.error("No PDF files found in Dropbox!")
            return
            
        # Log some info about the first few PDFs
        for i, pdf in enumerate(pdf_files[:3], 1):
            logger.info(f"PDF {i}: {pdf['name']} (size: {len(pdf['content'])} bytes)")
        
        # Limit to max_pdfs
        max_pdfs = 20
        if len(pdf_files) > max_pdfs:
            logger.info(f"Limiting to first {max_pdfs} PDFs out of {len(pdf_files)} total files")
            pdf_files = pdf_files[:max_pdfs]
        else:
            logger.info(f"Processing all {len(pdf_files)} PDFs")
        logger.info(f"Processing {len(pdf_files)} PDFs")
        
        # Initialize processors
        pdf_processor = PDFProcessor()
        structured_extractor = StructuredExtractor()
        summary_generator = ExecutiveSummaryGenerator(
            ExecutiveSummaryConfig(
                max_macro_trends=5,
                max_sector_insights=5,
                max_quotes=3,
                max_risks=5,
                max_recommendations=5
            )
        )
        email_handler = EmailHandler()
        
        # Process PDFs
        all_structured_data = []
        for i, pdf_file in enumerate(pdf_files, 1):
            try:
                logger.info(f"Processing PDF {i}/{len(pdf_files)}: {pdf_file['name']}")
                
                # Extract text with layout
                pdf_stream = io.BytesIO(pdf_file['content'])
                text = pdf_processor.extract_text_with_layout(pdf_stream)
                
                if not text.strip():
                    logger.warning(f"No text extracted from {pdf_file['name']}")
                    continue
                    
                logger.info(f"Successfully extracted {len(text)} characters from {pdf_file['name']}")
                
                # Extract structured data
                structured_data = structured_extractor.extract_financial_data(
                    text,
                    pdf_file['name'],
                    "1"  # Default page reference
                )
                
                if structured_data:
                    logger.info(f"Successfully extracted structured data from {pdf_file['name']}")
                    all_structured_data.append(structured_data)
                else:
                    logger.warning(f"No structured data extracted from {pdf_file['name']}")
                    
            except Exception as e:
                logger.error(f"Error processing {pdf_file['name']}: {e}", exc_info=True)
                continue
        
        # Combine all structured data
        logger.info("Generating executive summary...")
        combined_data = combine_structured_data(all_structured_data)
        
        # Generate executive summary
        executive_summary = summary_generator.generate_summary(combined_data)
        
        # Create HTML email
        logger.info("Creating HTML email...")
        html_email = email_handler.create_html_email(executive_summary)
        
        # Save the output
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save structured data
        with open(f"{output_dir}/structured_data.json", "w") as f:
            json.dump(combined_data, f, indent=2)
        
        # Save executive summary
        with open(f"{output_dir}/executive_summary.json", "w") as f:
            json.dump(executive_summary, f, indent=2)
        
        # Save HTML email
        with open(f"{output_dir}/email_output.html", "w") as f:
            f.write(html_email)
        
        logger.info(f"Test complete! Output saved to {output_dir}/")
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {e}", exc_info=True)
        raise

def combine_structured_data(data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine structured data from multiple PDFs.
    
    Args:
        data_list: List of structured data dictionaries
        
    Returns:
        Combined structured data
    """
    if not data_list:
        logger.warning("No structured data to combine")
        return {
            "numbers": [],
            "quotes": [],
            "dates": [],
            "key_points": [],
            "macro_trends": [],
            "sector_insights": [],
            "risks": [],
            "opportunities": []
        }
    
    combined = {
        "numbers": [],
        "quotes": [],
        "dates": [],
        "key_points": [],
        "macro_trends": [],
        "sector_insights": [],
        "risks": [],
        "opportunities": []
    }
    
    for data in data_list:
        for key in combined:
            if data.get(key):
                # Convert any dataclass objects to dictionaries before extending
                combined[key].extend(convert_to_dict(data[key]))
    
    return combined

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_pipeline())
