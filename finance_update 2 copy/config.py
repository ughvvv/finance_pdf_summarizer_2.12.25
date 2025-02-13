"""Configuration module for the finance update processor.

This module handles loading environment variables, setting up configuration parameters,
and validating the required settings for the application to run properly.
"""

import os
import logging
import pytz
from datetime import datetime
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Configuration for the finance update processor"""
    
    # Define all fields that will be used
    openai_key: str
    dropbox_refresh_token: str
    dropbox_app_key: str
    dropbox_app_secret: str
    email_host: str
    email_port: int
    sender_email: str
    email_password: str
    recipient_email: str
    batch_size: int
    max_concurrent_tasks: int
    token_limit: int
    http_proxy: str
    https_proxy: str

    def __init__(self):
        logger.debug("Initializing configuration")
        
        # API Keys
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.dropbox_refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
        self.dropbox_app_key = os.getenv('DROPBOX_APP_KEY')
        self.dropbox_app_secret = os.getenv('DROPBOX_APP_SECRET')
        
        # Email Settings
        self.email_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
        self.email_port = 465
        self.sender_email = os.getenv('EMAIL_USERNAME')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.recipient_email = "blakecole07@gmail.com"
        
        # Processing Settings
        self.batch_size = int(os.getenv('BATCH_SIZE', '2'))
        self.max_concurrent_tasks = int(os.getenv('MAX_CONCURRENT_TASKS', '15'))  # Increased default concurrency to match BatchProcessor
        self.token_limit = int(os.getenv('TOKEN_LIMIT', '12000'))  # Reduced from 100000 to stay within model limits
        
        # Chunk Manager Settings
        self.max_chunk_size = int(os.getenv('MAX_CHUNK_SIZE', '8000'))
        self.chunk_ratio = float(os.getenv('CHUNK_RATIO', '0.8'))
        self.token_ratio = float(os.getenv('TOKEN_RATIO', '1.3'))
        
        # Proxy Settings
        self.http_proxy = os.getenv('HTTP_PROXY')
        self.https_proxy = os.getenv('HTTPS_PROXY')
        
        # Validate and log configuration
        self._validate_config()
        self._log_config()
    
    def _log_config(self):
        """Log non-sensitive configuration settings"""
        logger.debug(f"Email Host: {self.email_host}")
        logger.debug(f"Email Port: {self.email_port}")
        logger.debug(f"Sender Email: {self.sender_email}")
        logger.debug(f"Recipient Email: {self.recipient_email}")
        logger.debug(f"Batch Size: {self.batch_size}")
        logger.debug(f"Max Concurrent Tasks: {self.max_concurrent_tasks}")
        logger.debug(f"Token Limit: {self.token_limit}")
        logger.debug(f"Max Chunk Size: {self.max_chunk_size}")
        logger.debug(f"Chunk Ratio: {self.chunk_ratio}")
        logger.debug(f"Token Ratio: {self.token_ratio}")
        if self.http_proxy:
            logger.debug(f"HTTP Proxy configured")
        if self.https_proxy:
            logger.debug(f"HTTPS Proxy configured")
    
    def _validate_config(self):
        """Validate required configuration settings"""
        required_settings = {
            'OPENAI_API_KEY': self.openai_key,
            'DROPBOX_REFRESH_TOKEN': self.dropbox_refresh_token,
            'DROPBOX_APP_KEY': self.dropbox_app_key,
            'DROPBOX_APP_SECRET': self.dropbox_app_secret,
            'EMAIL_USERNAME': self.sender_email,
            'EMAIL_PASSWORD': self.email_password
        }
        
        missing_settings = [
            key for key, value in required_settings.items()
            if not value
        ]
        
        if missing_settings:
            error_msg = f"Missing required environment variables: {', '.join(missing_settings)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.debug("Configuration validation successful")
    
    def get_dropbox_folder(self) -> str:
        """
        Get the Dropbox folder path by checking current date and rolling back until a valid folder is found.
        Returns the most recent valid folder path.
        """
        pacific_tz = pytz.timezone("US/Pacific")
        current_date = datetime.now(pacific_tz)
        max_days_back = 7  # Maximum number of days to look back
        
        for days_back in range(max_days_back):
            check_date = current_date - timedelta(days=days_back)
            
            # Format components with non-zero-padded day
            year = check_date.year
            month_name = check_date.strftime('%B')     # 'December'
            mon_abbr = check_date.strftime('%b')       # 'Dec'
            day = str(check_date.day)                  # '17' (no zero padding)

            # Construct folder path
            folder_path = f"/Current/{year}/{month_name}/{mon_abbr} {day}"
            logger.info(f"Checking Dropbox folder path: {folder_path}")
            
            return folder_path  # Return the path for the DropboxClient to validate

    @classmethod
    def create(cls) -> 'Config':
        """Factory method to create a Config instance with proper error handling"""
        try:
            return cls()
        except Exception as e:
            logger.error(f"Failed to create configuration: {str(e)}")
            raise
