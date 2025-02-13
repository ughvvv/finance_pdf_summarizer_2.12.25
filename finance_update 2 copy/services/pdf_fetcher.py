"""Service for fetching PDFs from Dropbox."""

import logging
from typing import List, Dict, Union, BinaryIO
from config import Config
from clients.dropbox_client import DropboxClient
from utils.exceptions import ProcessingError

logger = logging.getLogger(__name__)

class PDFFetcher:
    """Handles fetching PDFs from Dropbox."""
    
    def __init__(self, dropbox_client: DropboxClient):
        """
        Initialize PDFFetcher.
        
        Args:
            dropbox_client: Initialized Dropbox client
        """
        self.dropbox_client = dropbox_client
        
    async def fetch_pdfs(self, config: Config) -> List[Dict[str, Union[str, BinaryIO]]]:
        """
        Fetch PDF files from Dropbox.
        
        Args:
            config: Application configuration
            
        Returns:
            List of dictionaries containing file names and binary streams
            
        Raises:
            ProcessingError: If there's an error fetching PDFs
        """
        logger.info("Fetching PDF files from Dropbox...")
        try:
            pdf_files = await self.dropbox_client.fetch_reports(config)
            logger.info(f"Found {len(pdf_files)} PDF files")
            return pdf_files
        except Exception as e:
            logger.error(f"Error fetching PDF files: {e}", exc_info=True)
            raise ProcessingError(
                stage="pdf_fetch",
                details=f"Error fetching PDF files: {str(e)}",
                recovery_action="Check Dropbox connection and permissions"
            )
