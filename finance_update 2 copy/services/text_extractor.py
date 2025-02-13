"""Service for extracting and validating text from PDFs."""

import logging
from typing import Dict, Union, BinaryIO
from collections import Counter
from utils.pdf_processor import PDFProcessor
from utils.text_processor import TextProcessor
from utils.exceptions import ExtractionError
import re

# Configure logging
logger = logging.getLogger(__name__)
progress_logger = logging.getLogger('progress')
progress_logger.setLevel(logging.INFO)

# Constants for text validation - adjusted for financial documents
MIN_VALID_TEXT_LENGTH = 100  # Minimum text length
MAX_SPECIAL_CHAR_RATIO = 0.20  # Increased to allow more special characters
MIN_LINE_LENGTH = 15  # Reduced minimum line length for better capture
MIN_VALID_LINE_RATIO = 0.20  # Reduced to capture more reports

class PDFTextExtractor:
    """Handles PDF text extraction and validation."""

    def __init__(self):
        """Initialize PDFTextExtractor."""
        self.pdf_processor = PDFProcessor()
        self.error_counter = Counter()
        self.validation_stats = {
            'text_length': [],
            'total_lines': [],
            'valid_lines': [],
            'valid_line_ratio': [],
            'special_char_ratio': []
        }
        self.sample_extracts = []

    def _log_stage(self, stage: str, progress: float = None):
        """Log stage transition with optional progress."""
        status = f"STAGE: {stage}"
        if progress is not None:
            status += f" ({progress:.1f}% complete)"
        if self.error_counter:
            status += f"\nErrors: {dict(self.error_counter)}"
        if self.validation_stats:
            status += f"\nValidation Stats: {dict(self.validation_stats)}"
        progress_logger.info(status)

    def _log_sample_extract(self, text: str, filename: str, validation_result: bool):
        """Store sample extract with validation result."""
        sample = {
            'filename': filename,
            'preview': self._format_preview(text),
            'validation': validation_result,
            'stats': {
                'length': len(text),
                'lines': len(text.split('\n')),
                'special_char_ratio': sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text) if text else 0
            }
        }

        self.sample_extracts.append(sample)
        if len(self.sample_extracts) > 10:
            self.sample_extracts.pop(0)

        # Log current samples
        progress_logger.info(f"\nRecent Extraction Sample ({filename}):")
        progress_logger.info(f"- Preview: {sample['preview']}")
        progress_logger.info(f"- Validation: {'✓' if validation_result else '✗'}")
        progress_logger.info(f"- Stats: {sample['stats']}\n")

    async def extract(self, pdf_data: Dict[str, Union[str, BinaryIO]]) -> Dict[str, str]:
        """Extract and validate text from a PDF file."""
        try:
            filename = pdf_data['name']
            self._log_stage(f"Extracting {filename}")

            # Process the PDF file
            result = await self.pdf_processor.extract(pdf_data)
            if not result or not isinstance(result, dict) or 'text' not in result:
                raise ExtractionError(f"Failed to extract text from {filename}", "Invalid extraction result")

            # Clean the text before validation
            cleaned_text = self._clean_boilerplate(result['text'])
            result['text'] = cleaned_text

            # Validate extracted text
            validation_details = self._validate_extracted_text(cleaned_text)
            
            # Update validation stats
            stats = validation_details['stats']
            for key, value in stats.items():
                if key in self.validation_stats:
                    self.validation_stats[key].append(value)

            # Log sample with validation result
            self._log_sample_extract(cleaned_text, filename, validation_details['passed'])

            if validation_details['passed']:
                progress_logger.info(f"✓ Successfully extracted {filename}")
                progress_logger.info(f"Validation details: {validation_details['stats']}")
                return result
            else:
                # Accept if we have enough valid lines, even if ratio is low
                if validation_details['stats']['valid_lines'] >= 30:
                    progress_logger.info(f"⚠ Accepting {filename} despite validation failures due to sufficient valid lines")
                    return result
                
                self.error_counter['validation_failures'] += 1
                logger.warning(f"✗ Invalid text extracted from {filename}")
                logger.warning(f"Validation failures: {validation_details['failures']}")
                raise ExtractionError(
                    f"Invalid text extracted from {filename}",
                    f"Validation failures: {validation_details['failures']}"
                )

        except Exception as e:
            self.error_counter['extraction_errors'] += 1
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            raise ExtractionError(str(e), "PDF processing failed")

    def _validate_extracted_text(self, text: str) -> Dict:
        """Validate extracted text quality with detailed reporting."""
        validation_result = {
            'passed': False,
            'stats': {},
            'failures': []
        }

        if not text or not isinstance(text, str):
            validation_result['failures'].append('No text content')
            return validation_result

        # Basic length check
        text_length = len(text.strip())
        if text_length < MIN_VALID_TEXT_LENGTH:
            validation_result['failures'].append(
                f'Text too short: {text_length} chars (min: {MIN_VALID_TEXT_LENGTH})'
            )

        # Line quality checks
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            validation_result['failures'].append('No valid lines found')

        valid_lines = [line for line in lines if len(line) >= MIN_LINE_LENGTH]
        valid_line_ratio = len(valid_lines) / len(lines) if lines else 0

        if valid_line_ratio < MIN_VALID_LINE_RATIO:
            validation_result['failures'].append(
                f'Too few valid lines: {valid_line_ratio:.1%} (min: {MIN_VALID_LINE_RATIO:.1%})'
            )

        # Special character ratio
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        special_char_ratio = special_chars / len(text) if text else 1

        if special_char_ratio > MAX_SPECIAL_CHAR_RATIO:
            validation_result['failures'].append(
                f'Too many special characters: {special_char_ratio:.1%} (max: {MAX_SPECIAL_CHAR_RATIO:.1%})'
            )

        # Store statistics
        validation_result['stats'] = {
            'text_length': text_length,
            'total_lines': len(lines),
            'valid_lines': len(valid_lines),
            'valid_line_ratio': valid_line_ratio,
            'special_char_ratio': special_char_ratio
        }

        # Set passed if no failures
        validation_result['passed'] = len(validation_result['failures']) == 0

        return validation_result

    def _clean_boilerplate(self, text: str) -> str:
        """Remove common boilerplate text from financial documents."""
        lines = text.split('\n')
        cleaned_lines = []

        skip_patterns = [
            r'^disclaimer',
            r'^confidential',
            r'^all rights reserved',
            r'^for institutional',
            r'^not for distribution',
            r'^copyright',
            r'^\s*page\s+\d+\s*$',
            r'^\s*\d+\s*$',  # Page numbers
            r'^strictly\s+private',
            r'^proprietary\s+and\s+confidential',
            r'^this\s+document\s+is\s+solely\s+for',
            r'^important\s+disclosures\s+appear',
            r'^please\s+see\s+important\s+disclosures'
        ]

        header_footer_buffer = 3  # Lines to skip at start/end
        content_lines = lines[header_footer_buffer:-header_footer_buffer]

        for line in content_lines:
            if not any(re.match(pattern, line.lower()) for pattern in skip_patterns):
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _format_preview(self, text: str, max_length: int = 100) -> str:
        """Format text preview while preserving structure."""
        if not text:
            return ""

        # Clean up whitespace while preserving structure
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        preview = ' '.join(lines)[:max_length]

        return f"{preview}..." if len(preview) == max_length else preview
