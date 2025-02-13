"""Module for processing PDF files."""

import io
import logging
from typing import Dict, Union, Tuple, BinaryIO
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from utils.text_processor import TextProcessor

# Configure logging
logger = logging.getLogger(__name__)
# Reduce pdfminer logging verbosity
logging.getLogger('pdfminer').setLevel(logging.ERROR)

class PDFProcessor:
    """Handles PDF processing with streaming and parallel processing"""

    def __init__(self, max_workers: int = 4):
        """Initialize PDFProcessor."""
        self.text_processor = TextProcessor()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def extract(self, pdf_data: Dict) -> Dict:
        """
        Extract text from a PDF file asynchronously.
        
        Args:
            pdf_data: Dictionary containing PDF file information
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        try:
            # Run CPU-intensive PDF processing in a thread pool
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.process_pdf,
                pdf_data
            )
            return result
        except Exception as e:
            logger.error(f"Error in async PDF extraction: {str(e)}")
            raise

    def extract_text_with_layout(self, pdf_stream: BinaryIO) -> str:
        """
        Extract text from PDF with layout analysis.
        
        Args:
            pdf_stream: PDF file stream
            
        Returns:
            Extracted text with preserved layout
        """
        try:
            # Set up PDF resources
            resource_manager = PDFResourceManager()
            fake_file_handle = io.StringIO()
            
            # Configure layout parameters
            laparams = LAParams(
                line_margin=0.5,
                word_margin=0.1,
                char_margin=2.0,
                boxes_flow=0.5,
                detect_vertical=True,
                all_texts=True
            )
            
            # Set up converter
            converter = TextConverter(
                resource_manager, 
                fake_file_handle, 
                laparams=laparams
            )
            
            # Set up interpreter
            page_interpreter = PDFPageInterpreter(resource_manager, converter)
            
            # Process each page
            for page in PDFPage.get_pages(pdf_stream):
                page_interpreter.process_page(page)
                
            # Get text
            text = fake_file_handle.getvalue()
            
            # Clean up
            converter.close()
            fake_file_handle.close()
            
            return text

        except Exception as e:
            logger.error(f"Error extracting text with layout: {str(e)}")
            raise

    @staticmethod
    def clean_extracted_text(text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        # Remove control characters while preserving basic formatting
        text = ''.join(char if char.isprintable() or char in '\n\t' else ' ' for char in text)
        
        # Normalize whitespace while preserving paragraph breaks
        text = re.sub(r'[\r\f\v]', '\n', text)  # Convert other breaks to newlines
        text = re.sub(r' *\n *', '\n', text)    # Clean up spaces around newlines
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive newlines
        text = re.sub(r' {2,}', ' ', text)      # Remove multiple spaces
        
        # Remove empty lines at start/end
        text = text.strip()
        
        return text

    def process_pdf(self, pdf_data: Union[Dict, Tuple[str, BinaryIO]]) -> Dict:
        """
        Process a single PDF file with improved error handling.
        
        Args:
            pdf_data: Either a dictionary with 'name' and 'content' keys,
                    or a tuple of (filename, file_stream)
            
        Returns:
            Dictionary containing:
            - text: Extracted text
            - file_name: Original filename
            - preview: First 100 characters of text
            - error: Error message if any
        """
        file_name = None
        try:
            # Get file name and stream
            if isinstance(pdf_data, dict):
                file_name = pdf_data.get('name', '')
                content = pdf_data.get('content')
                if not content:
                    raise ValueError(f"No content provided for {file_name}")
                file_stream = io.BytesIO(content)
            else:
                file_name, file_stream = pdf_data

            if not file_stream:
                raise ValueError(f"No valid file stream for {file_name}")
            
            # Extract text with layout preservation
            text = self.extract_text_with_layout(file_stream)
            
            # Clean the extracted text
            text = self.clean_extracted_text(text)
            
            # Validate text
            if not text.strip():
                raise ValueError(f"No text extracted from {file_name}")
            
            # Create preview
            preview = text[:100] + "..." if len(text) > 100 else text
            
            return {
                'text': text,
                'file_name': file_name,
                'preview': preview
            }
            
        except Exception as e:
            error_msg = f"Error processing PDF {file_name if file_name else 'unknown'}: {str(e)}"
            logger.error(error_msg)
            return {
                'text': '',
                'file_name': file_name if file_name else 'unknown',
                'preview': '',
                'error': error_msg
            }
