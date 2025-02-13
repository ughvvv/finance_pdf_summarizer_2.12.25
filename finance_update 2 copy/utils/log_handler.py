"""Custom logging handler that manages log file size based on token count."""

import os
import logging
from typing import Optional
import re

class TokenSizeRotatingFileHandler(logging.FileHandler):
    """A file handler that rotates the log file when it exceeds a token threshold."""
    
    def __init__(
        self,
        filename: str,
        mode: str = 'a',
        encoding: Optional[str] = None,
        delay: bool = False,
        max_tokens: int = 120000,  # Default 120k tokens
        chars_per_token: int = 4   # Approximate chars per token
    ):
        """Initialize the handler with a maximum token limit.
        
        Args:
            filename: Log file path
            mode: File open mode
            encoding: File encoding
            delay: Delay file opening
            max_tokens: Maximum number of tokens before rotation
            chars_per_token: Approximate number of characters per token
        """
        super().__init__(filename, mode, encoding, delay)
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.max_chars = max_tokens * chars_per_token
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, checking file size before writing."""
        try:
            if self.should_rotate():
                self.do_rotation()
            super().emit(record)
        except Exception:
            self.handleError(record)
    
    def should_rotate(self) -> bool:
        """Check if the log file should be rotated based on size."""
        if not os.path.exists(self.baseFilename):
            return False
            
        file_size = os.path.getsize(self.baseFilename)
        return file_size > self.max_chars
    
    def do_rotation(self) -> None:
        """Clear the log file when rotation is needed."""
        if self.stream:
            self.stream.close()
            self.stream = None
            
        # Clear the file
        with open(self.baseFilename, 'w') as f:
            f.write("Log file cleared due to size limit\n")
            
        if not self.delay:
            self.stream = self._open()
