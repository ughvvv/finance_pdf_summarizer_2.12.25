"""Dropbox client for fetching reports."""

import logging
from typing import List, Dict, Union, BinaryIO
import io
import dropbox
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dropbox.files import FileMetadata, ListFolderResult
from dropbox.exceptions import ApiError
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

class DropboxClient:
    """Client for interacting with Dropbox API."""
    
    def __init__(self, refresh_token: str, app_key: str, app_secret: str, max_workers: int = 5):
        """
        Initialize Dropbox client.
        
        Args:
            refresh_token: OAuth2 refresh token
            app_key: Dropbox app key
            app_secret: Dropbox app secret
            max_workers: Maximum number of concurrent downloads
        """
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret
        )
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def _list_folder_recursive(self, path: str = "") -> List[FileMetadata]:
        """
        List all files in a folder recursively, handling pagination.
        
        Args:
            path: Path to list files from
            
        Returns:
            List of FileMetadata objects
        """
        try:
            logger.info(f"Listing files in Dropbox folder: {path}")
            files = []
            
            # Try to list the folder contents
            try:
                result = self.dbx.files_list_folder(path, recursive=True)
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    logger.warning(f"Path {path} not found in Dropbox")
                    return []
                raise
            
            while True:
                for entry in result.entries:
                    if isinstance(entry, FileMetadata):
                        logger.info(f"Found file: {entry.path_display}")
                        files.append(entry)
                
                # Check if there are more files to fetch
                if not result.has_more:
                    break
                    
                result = self.dbx.files_list_folder_continue(result.cursor)
            
            logger.info(f"Found {len(files)} total files in {path}")
            return files
            
        except ApiError as e:
            if e.error.is_path():
                logger.warning(f"Path {path} not found in Dropbox")
                return []
            raise

    async def _download_file(self, entry: FileMetadata, total_files: int, index: int) -> Dict[str, Union[str, bytes]]:
        """
        Download a single file from Dropbox asynchronously.
        
        Args:
            entry: FileMetadata object
            total_files: Total number of files to download
            index: Current file index
            
        Returns:
            Dictionary containing file metadata and content
        """
        try:
            logger.info(f"Downloading {entry.path_display} ({index}/{total_files})...")
            
            # Use ThreadPoolExecutor for blocking Dropbox API calls
            metadata, response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.dbx.files_download(entry.path_lower)
            )
            
            # Read the content
            content = response.raw.read()
            
            logger.info(f"Successfully downloaded {entry.name} ({len(content)} bytes)")
            
            return {
                'name': entry.name,
                'path': entry.path_display,
                'content': content
            }
        except ApiError as e:
            logger.error(f"Error downloading {entry.path_display}: {e}")
            return None
        
    async def fetch_reports(self, config) -> List[Dict[str, Union[str, BinaryIO]]]:
        """
        Fetch PDF reports from Dropbox using concurrent downloads.
        Tries multiple dates until finding a folder with PDF files.
        
        Args:
            config: Application configuration
            
        Returns:
            List of dictionaries containing file names and binary streams
        """
        try:
            pacific_tz = pytz.timezone("US/Pacific")
            current_date = datetime.now(pacific_tz)
            max_days_back = 7  # Maximum number of days to look back
            
            for days_back in range(max_days_back):
                check_date = current_date - timedelta(days=days_back)
                
                # Format components with non-zero-padded day
                year = check_date.year
                month_name = check_date.strftime('%B')
                mon_abbr = check_date.strftime('%b')
                day = str(check_date.day)
                
                # Construct folder path
                folder_path = f"/Current/{year}/{month_name}/{mon_abbr} {day}"
                logger.info(f"Checking Dropbox folder path: {folder_path}")
                
                # List all files recursively
                all_files = self._list_folder_recursive(folder_path)
                
                # Filter for PDFs and sort by modification date
                pdf_entries = [
                    entry for entry in all_files 
                    if isinstance(entry, FileMetadata) and entry.name.lower().endswith('.pdf')
                ]
                
                if pdf_entries:
                    logger.info(f"Found PDF files in folder: {folder_path}")
                    pdf_entries.sort(key=lambda x: x.server_modified, reverse=True)
                    break
                else:
                    logger.info(f"No PDF files found in {folder_path}, checking previous day...")
                    
            if not pdf_entries:
                logger.warning(f"No PDF files found in the last {max_days_back} days")
                return []
            
            # Create download tasks for each PDF
            total_files = len(pdf_entries)
            download_tasks = [
                self._download_file(entry, total_files, i)
                for i, entry in enumerate(pdf_entries, 1)
            ]
            
            # Download files concurrently
            pdf_files = await asyncio.gather(*download_tasks)
            
            # Filter out failed downloads
            pdf_files = [f for f in pdf_files if f is not None]
            
            logger.info(f"Successfully downloaded {len(pdf_files)} PDF files")
            return pdf_files
            
        except ApiError as e:
            logger.error(f"Dropbox API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching reports: {e}")
            raise
