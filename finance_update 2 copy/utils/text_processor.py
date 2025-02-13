import re
import string
import logging
import nltk
import tiktoken
import functools
import gc
from typing import List, Optional

logger = logging.getLogger(__name__)

def get_encoding_for_model(model: str) -> tiktoken.Encoding:
    """Get the appropriate encoding for a specific model"""
    try:
        if model.startswith('o1'):
            return tiktoken.get_encoding("cl100k_base")  # Used by o1 models
        elif model.startswith('gpt-4'):
            return tiktoken.encoding_for_model("gpt-4")
        else:
            return tiktoken.encoding_for_model("gpt-3.5-turbo")
    except Exception as e:
        logger.warning(f"Error getting encoding for model {model}, falling back to gpt-3.5-turbo: {e}")
        return tiktoken.encoding_for_model("gpt-3.5-turbo")

@functools.lru_cache(maxsize=256)  # Reduced cache size
def get_token_count(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Get token count for text with model-specific encoding"""
    encoding = get_encoding_for_model(model)
    return len(encoding.encode(text))

class TextProcessor:
    """Handles text processing operations with improved efficiency"""

    @staticmethod
    def safe_slice(text: str, start: int = None, end: int = None, default: str = "") -> str:
        """
        Safely slice text, handling cases where text might not be a string.
        
        Args:
            text: Text to slice
            start: Start index
            end: End index
            default: Default value if slicing fails
            
        Returns:
            Sliced text or default value if operation fails
        """
        try:
            if not isinstance(text, str):
                logger.error(f"Expected string but got {type(text)}")
                return str(text)
            if start is None:
                return text
            return text[start:end] if end else text[start:]
        except Exception as e:
            logger.error(f"Error slicing text: {e}")
            return default

    @staticmethod
    def format_preview(text: str, max_length: int = 100) -> str:
        """
        Format text preview while preserving structure.
        
        Args:
            text: Text to preview
            max_length: Maximum length of preview
            
        Returns:
            Formatted preview text
        """
        if isinstance(text, tuple):
            text = text[0]
        if not text:
            return ""
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Get first few lines
        lines = text.split('\n')
        preview_lines = []
        current_length = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Add line length plus newline
            if current_length + len(line) + 1 > max_length:
                # If this is the first line, take a portion of it
                if not preview_lines:
                    preview_lines.append(line[:max_length-3] + "...")
                else:
                    preview_lines.append("...")
                break
                
            preview_lines.append(line)
            current_length += len(line) + 1
            
            if current_length >= max_length:
                preview_lines.append("...")
                break
        
        return ' '.join(preview_lines)
    
    # Compile regex patterns once at class level
    _disclaimer_pattern = re.compile(
        r"(?:DISCLAIMER|LEGAL NOTICE|IMPORTANT DISCLOSURE|CONFIDENTIAL|"
        r"This (?:report|document|material) is (?:confidential|for informational purposes only)|"
        r"Not intended as investment advice|"
        r"Past performance is not indicative of future results|"
        r"The opinions expressed herein|"
        r"This material is confidential|"
        r"without any express or implied warranty|"
        r"All rights reserved|"
        r"©\s*\d{4}|"
        r"Proprietary and Confidential|"
        r"Do not distribute|"
        r"For institutional investors only).+?(?=\n\n|\Z)",
        re.IGNORECASE | re.DOTALL
    )
    
    _whitespace_pattern = re.compile(r'\s+')
    _sentence_pattern = re.compile(r'(?<=[.!?])\s+')
    
    # Common financial symbols to preserve
    _preserve_symbols = {'$', '€', '£', '¥', '%', '±', '∆', '→', '↑', '↓', '≈', '≠', '≤', '≥'}

    @staticmethod
    def remove_legal_disclaimers(text: str) -> str:
        """Removes legal disclaimers from the text based on common phrases."""
        return TextProcessor._disclaimer_pattern.sub('', text)

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Cleans text while preserving important financial symbols and formatting.
        """
        if not text:
            return ""
            
        # Split into lines to preserve structure
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                cleaned_lines.append('')
                continue
                
            # Create a list of characters to keep
            cleaned_chars = []
            for char in line:
                # Keep if it's a preserved symbol
                if char in TextProcessor._preserve_symbols:
                    cleaned_chars.append(char)
                # Keep if it's a printable character or whitespace
                elif char.isprintable() or char.isspace():
                    cleaned_chars.append(char)
                # Replace other characters with space
                else:
                    cleaned_chars.append(' ')
            
            # Join characters and normalize whitespace
            cleaned_line = ''.join(cleaned_chars)
            cleaned_line = TextProcessor._whitespace_pattern.sub(' ', cleaned_line)
            cleaned_line = cleaned_line.strip()
            
            if cleaned_line:
                cleaned_lines.append(cleaned_line)
        
        # Join lines with proper spacing
        text = '\n'.join(cleaned_lines)
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """Split text into sentences with improved handling of financial text."""
        try:
            # Handle common financial abbreviations
            text = re.sub(r'(?<=\d)\.(?=\d)', '[DOT]', text)  # Preserve decimal points
            text = re.sub(r'(?<=\w)\.(?=\w)', '[DOT]', text)  # Preserve abbreviations
            
            sentences = nltk.sent_tokenize(text)
            
            # Restore decimal points and abbreviations
            sentences = [s.replace('[DOT]', '.') for s in sentences]
            
            return sentences
        except Exception as e:
            logger.warning(f"NLTK tokenization failed, using regex splitting: {e}")
            # Fallback to regex splitting
            splits = TextProcessor._sentence_pattern.split(text)
            return [s.strip() for s in splits if s.strip()]

    @staticmethod
    def chunk_large_text(text: str, model_context_limit: int, model: str = "gpt-3.5-turbo") -> List[str]:
        """Pre-chunk very large texts before processing with improved memory management"""
        try:
            # Reserve 25% for prompt template and safety buffer
            target_size = int(model_context_limit * 0.75)
            chunks = []
            
            # Split into sentences
            sentences = TextProcessor.split_into_sentences(text)
            current_chunk = []
            current_size = 0

            for sentence in sentences:
                sentence_tokens = get_token_count(sentence, model)
                
                if sentence_tokens > target_size:
                    # Handle oversized sentences
                    if current_chunk:
                        chunk_text = ' '.join(current_chunk)
                        chunks.append(chunk_text)
                        del current_chunk[:]  # Clear list while keeping reference
                        current_size = 0
                    
                    # Split oversized sentence
                    words = sentence.split()
                    temp_chunk = []
                    temp_size = 0
                    
                    for word in words:
                        word_tokens = get_token_count(word + ' ', model)
                        if temp_size + word_tokens > target_size:
                            if temp_chunk:
                                chunks.append(' '.join(temp_chunk))
                                del temp_chunk[:]
                            temp_chunk = [word]
                            temp_size = word_tokens
                        else:
                            temp_chunk.append(word)
                            temp_size += word_tokens
                    
                    if temp_chunk:
                        chunks.append(' '.join(temp_chunk))
                
                elif current_size + sentence_tokens > target_size:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [sentence]
                    current_size = sentence_tokens
                else:
                    current_chunk.append(sentence)
                    current_size += sentence_tokens

            if current_chunk:
                chunks.append(' '.join(current_chunk))

            # Clear references to large strings
            del sentences
            gc.collect()

            return chunks

        except Exception as e:
            logger.error(f"Error in chunk_large_text: {e}", exc_info=True)
            # Fallback with proper token limit respect
            chunks = []
            remaining_text = text
            while remaining_text:
                # Get chunk size that respects token limit
                chunk_size = target_size
                while chunk_size > 0:
                    chunk = remaining_text[:chunk_size]
                    if get_token_count(chunk, model) <= target_size:
                        break
                    chunk_size = int(chunk_size * 0.9)  # Reduce by 10% and try again
                
                if chunk_size == 0:
                    logger.error("Could not create valid chunk, text may be malformed")
                    break
                
                chunks.append(chunk)
                remaining_text = remaining_text[chunk_size:].lstrip()
            
            return chunks

    @staticmethod
    def merge_chunks(chunks: List[str], max_size: int, model: str = "gpt-3.5-turbo") -> List[str]:
        """Merge chunks while respecting token limits with improved efficiency"""
        if not chunks:
            return chunks

        merged = []
        current_chunks = []
        current_size = 0

        for chunk in chunks:
            chunk_size = get_token_count(chunk, model)
            
            # Handle oversized chunks
            if chunk_size > max_size:
                if current_chunks:
                    merged.append(' '.join(current_chunks))
                    del current_chunks[:]
                    current_size = 0
                # Split oversized chunk
                sub_chunks = TextProcessor.chunk_large_text(chunk, max_size, model)
                merged.extend(sub_chunks)
                continue

            if current_size + chunk_size <= max_size:
                current_chunks.append(chunk)
                current_size += chunk_size
            else:
                if current_chunks:
                    merged.append(' '.join(current_chunks))
                    del current_chunks[:]
                current_chunks = [chunk]
                current_size = chunk_size

        if current_chunks:
            merged.append(' '.join(current_chunks))

        # Clear references to help garbage collection
        del current_chunks
        gc.collect()

        return merged

    @staticmethod
    def get_token_count(text: str, model: str = "gpt-3.5-turbo") -> int:
        """Get token count for text with model-specific encoding"""
        return get_token_count(text, model)
