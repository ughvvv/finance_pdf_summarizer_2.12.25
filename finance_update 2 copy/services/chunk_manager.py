"""Service for managing text chunking strategies."""

import re
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from prometheus_client import Histogram, Counter

from utils.exceptions import ChunkError, create_error_report

logger = logging.getLogger(__name__)

# Metrics
CHUNK_PROCESSING_TIME = Histogram(
    'chunk_processing_seconds',
    'Time spent processing chunks',
    ['operation', 'status']
)

CHUNK_OPERATIONS = Counter(
    'chunk_operations_total',
    'Total chunking operations',
    ['operation', 'status']
)

@dataclass
class ChunkMetadata:
    """Metadata for a text chunk."""
    index: int
    total_chunks: int
    token_count: int
    sentence_count: int
    paragraph_count: int

class ChunkManager:
    """Handles text chunking strategies and optimization."""

    def __init__(self, max_chunk_size: int = 8000):
        """
        Initialize ChunkManager.
        
        Args:
            max_chunk_size: Maximum tokens per chunk
            
        Raises:
            ChunkError: If initialization parameters are invalid
        """
        if max_chunk_size <= 0:
            raise ChunkError(
                "Invalid max_chunk_size",
                chunk_size=max_chunk_size,
                recovery_action="Set max_chunk_size to a positive integer"
            )
            
        self.max_chunk_size = max_chunk_size
        self.token_ratio = 1.3  # Estimated ratio of tokens to words
        
        # Paragraph break patterns
        self.paragraph_breaks = [
            r'\n\s*\n',           # Double newline
            r'\n\s*[•\-\*]\s*',   # Bullet points
            r'\n\s*\d+\.\s*',     # Numbered lists
            r'\n\s*[A-Z][\w\s]+:' # Section headers
        ]
        
        # Sentence end patterns
        self.sentence_ends = [
            r'(?<=[.!?])\s+(?=[A-Z])',
            r'(?<=\n)\s*(?=[A-Z])'
        ]

    def chunk_text(self, text: str, preserve_context: bool = True, max_tokens: Optional[int] = None) -> List[Tuple[str, ChunkMetadata]]:
        """
        Split text into optimal chunks while preserving context.
        
        Args:
            text: Text to chunk
            preserve_context: Whether to preserve paragraph/section context
            max_tokens: Optional maximum tokens per chunk (overrides max_chunk_size)
            
        Returns:
            List of (chunk_text, chunk_metadata) tuples
            
        Raises:
            ChunkError: If chunking fails or parameters are invalid
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            if not text:
                raise ChunkError(
                    "Empty text provided",
                    text_length=0,
                    recovery_action="Provide non-empty text for chunking"
                )
                
            effective_max_tokens = max_tokens if max_tokens is not None else self.max_chunk_size
            
            if effective_max_tokens <= 0:
                raise ChunkError(
                    "Invalid max_tokens value",
                    chunk_size=effective_max_tokens,
                    recovery_action="Set max_tokens to a positive integer"
                )
            # First split into paragraphs
            paragraphs = self._split_paragraphs(text)
            
            # Initialize chunks
            chunks = []
            current_chunk = []
            current_token_count = 0
            current_sentence_count = 0
            
            # Track metrics
            CHUNK_OPERATIONS.labels(operation='split_paragraphs', status='success').inc()

            for para in paragraphs:
                # Estimate tokens in paragraph
                para_tokens = self._estimate_tokens(para)
                
                # If paragraph alone exceeds chunk size, split it

                if para_tokens > effective_max_tokens:
                    # Process current chunk if not empty
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk,
                            current_token_count,
                            current_sentence_count
                        ))
                        current_chunk = []
                        current_token_count = 0
                        current_sentence_count = 0
                    
                    # Split large paragraph
                    para_chunks = self._split_large_paragraph(para, effective_max_tokens)
                    chunks.extend(para_chunks)
                    continue
            
                # Check if adding paragraph exceeds chunk size
                if current_token_count + para_tokens > effective_max_tokens:
                    # Create new chunk
                    chunks.append(self._create_chunk(
                        current_chunk,
                        current_token_count,
                        current_sentence_count
                    ))
                    current_chunk = []
                    current_token_count = 0
                    current_sentence_count = 0
                
                # Add paragraph to current chunk
                current_chunk.append(para)
                current_token_count += para_tokens
                current_sentence_count += len(self._split_sentences(para))
        
            # Add final chunk if not empty
            if current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk,
                    current_token_count,
                    current_sentence_count
                ))
        
            # Add metadata to chunks
            result = [
                (chunk[0], ChunkMetadata(
                    index=i + 1,
                    total_chunks=len(chunks),
                    token_count=chunk[1],
                    sentence_count=chunk[2],
                    paragraph_count=len(chunk[0].split('\n\n'))
                ))
                for i, chunk in enumerate(chunks)
            ]
            
            # Record success metrics
            duration = time.time() - start_time
            CHUNK_PROCESSING_TIME.labels(operation='chunk_text', status='success').observe(duration)
            CHUNK_OPERATIONS.labels(operation='chunk_text', status='success').inc()
            
            return result
            
        except Exception as e:
            # Record failure metrics
            duration = time.time() - start_time
            CHUNK_PROCESSING_TIME.labels(operation='chunk_text', status='failure').observe(duration)
            CHUNK_OPERATIONS.labels(operation='chunk_text', status='failure').inc()
            
            if not isinstance(e, ChunkError):
                e = ChunkError(
                    f"Failed to chunk text: {str(e)}",
                    text_length=len(text) if text else 0,
                    chunk_size=effective_max_tokens,
                    recovery_action="Check input text and chunking parameters"
                )
            
            logger.error(f"Chunking error: {create_error_report(e)}")
            raise e

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs using multiple break patterns."""
        # Combine all paragraph break patterns
        pattern = '|'.join(f'({p})' for p in self.paragraph_breaks)
        
        # Split and clean
        paragraphs = re.split(pattern, text)
        return [p.strip() for p in paragraphs if p and p.strip()]

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences using multiple end patterns."""
        # Combine all sentence end patterns
        pattern = '|'.join(f'({p})' for p in self.sentence_ends)
        
        # Split and clean
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s and s.strip()]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text."""
        # Simple estimation based on word count
        words = len(text.split())
        return int(words * self.token_ratio)

    def _split_large_paragraph(self, paragraph: str, effective_max_chunk: int) -> List[Tuple[str, int, int]]:
        """Split large paragraph into smaller chunks."""
        chunks = []
        sentences = self._split_sentences(paragraph)
        
        current_chunk = []
        current_token_count = 0
        current_sentence_count = 0
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            
            # If single sentence exceeds chunk size, split it
            if sentence_tokens > effective_max_chunk:
                # Process current chunk if not empty
                if current_chunk:
                    chunks.append((
                        ' '.join(current_chunk),
                        current_token_count,
                        current_sentence_count
                    ))
                    current_chunk = []
                    current_token_count = 0
                    current_sentence_count = 0
                
                # Split sentence into smaller pieces
                words = sentence.split()
                current_piece = []
                current_piece_tokens = 0
                
                for word in words:
                    word_tokens = self._estimate_tokens(word)
                    if current_piece_tokens + word_tokens > effective_max_chunk:
                        chunks.append((
                            ' '.join(current_piece),
                            current_piece_tokens,
                            1
                        ))
                        current_piece = []
                        current_piece_tokens = 0
                    
                    current_piece.append(word)
                    current_piece_tokens += word_tokens
                
                if current_piece:
                    chunks.append((
                        ' '.join(current_piece),
                        current_piece_tokens,
                        1
                    ))
                continue
            
            # Check if adding sentence exceeds chunk size
            if current_token_count + sentence_tokens > effective_max_chunk:
                chunks.append((
                    ' '.join(current_chunk),
                    current_token_count,
                    current_sentence_count
                ))
                current_chunk = []
                current_token_count = 0
                current_sentence_count = 0
            
            current_chunk.append(sentence)
            current_token_count += sentence_tokens
            current_sentence_count += 1
        
        # Add final chunk if not empty
        if current_chunk:
            chunks.append((
                ' '.join(current_chunk),
                current_token_count,
                current_sentence_count
            ))
        
        return chunks

    def _create_chunk(
        self,
        paragraphs: List[str],
        token_count: int,
        sentence_count: int
    ) -> Tuple[str, int, int]:
        """Create a chunk from paragraphs with metadata."""
        return (
            '\n\n'.join(paragraphs),
            token_count,
            sentence_count
        )

    def optimize_chunks(
        self,
        chunks: List[Tuple[str, ChunkMetadata]],
        target_size: int
    ) -> List[Tuple[str, ChunkMetadata]]:
        """
        Optimize chunk sizes to better match target size.
        
        Args:
            chunks: List of text chunks with metadata
            target_size: Target token count per chunk
            
        Returns:
            Optimized chunks
        """
        if not chunks:
            return []
            
        # If chunks are too small, combine them
        if all(meta.token_count < target_size * 0.5 for _, meta in chunks):
            return self._combine_small_chunks(chunks, target_size)
            
        # If chunks are too large, split them
        if any(meta.token_count > target_size * 1.5 for _, meta in chunks):
            return self._split_large_chunks(chunks, target_size)
            
        return chunks

    def _combine_small_chunks(
        self,
        chunks: List[Tuple[str, ChunkMetadata]],
        target_size: int
    ) -> List[Tuple[str, ChunkMetadata]]:
        """Combine small chunks to better match target size."""
        optimized = []
        current_texts = []
        current_token_count = 0
        current_sentence_count = 0
        current_para_count = 0
        
        for text, meta in chunks:
            if current_token_count + meta.token_count > target_size:
                # Create new chunk
                if current_texts:
                    combined_text = '\n\n'.join(current_texts)
                    optimized.append((
                        combined_text,
                        ChunkMetadata(
                            index=len(optimized) + 1,
                            total_chunks=len(chunks),
                            token_count=current_token_count,
                            sentence_count=current_sentence_count,
                            paragraph_count=current_para_count
                        )
                    ))
                    current_texts = []
                    current_token_count = 0
                    current_sentence_count = 0
                    current_para_count = 0
            
            current_texts.append(text)
            current_token_count += meta.token_count
            current_sentence_count += meta.sentence_count
            current_para_count += meta.paragraph_count
        
        # Add final chunk
        if current_texts:
            combined_text = '\n\n'.join(current_texts)
            optimized.append((
                combined_text,
                ChunkMetadata(
                    index=len(optimized) + 1,
                    total_chunks=len(chunks),
                    token_count=current_token_count,
                    sentence_count=current_sentence_count,
                    paragraph_count=current_para_count
                )
            ))
        
        return optimized

    def _split_large_chunks(
        self,
        chunks: List[Tuple[str, ChunkMetadata]],
        target_size: int
    ) -> List[Tuple[str, ChunkMetadata]]:
        """Split large chunks to better match target size."""
        optimized = []
        
        for text, meta in chunks:
            if meta.token_count > target_size * 1.5:
                # Rechunk the large chunk
                new_chunks = self.chunk_text(text)
                optimized.extend(new_chunks)
            else:
                optimized.append((text, meta))
        
        # Update indices
        return [
            (text, ChunkMetadata(
                index=i + 1,
                total_chunks=len(optimized),
                token_count=meta.token_count,
                sentence_count=meta.sentence_count,
                paragraph_count=meta.paragraph_count
            ))
            for i, (text, meta) in enumerate(optimized)
        ]
