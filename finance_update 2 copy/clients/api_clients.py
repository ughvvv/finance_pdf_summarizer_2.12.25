"""Module for API client interactions."""

import io
import logging
import backoff
import dropbox
import asyncio
import httpx
from datetime import datetime
from typing import List, Tuple, Dict
from openai import AsyncOpenAI
from dropbox.exceptions import DropboxException, AuthError
from config import Config
from constants import MODEL_CONFIGS, PROMPT_TEMPLATES
from utils.text_processor import get_token_count

logger = logging.getLogger(__name__)

class ProcessingError(Exception):
    def __init__(self, stage: str, details: str, recovery_action: str = None):
        self.stage = stage
        self.details = str(details)  # Ensure details is always a string
        self.recovery_action = recovery_action
        super().__init__(f"Error in {stage}: {self.details}")

class DropboxClient:
    """Handles Dropbox operations with improved error handling and retries"""

    def __init__(self, refresh_token: str, app_key: str, app_secret: str):
        """Initialize Dropbox client with proper OAuth2 handling"""
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.dbx = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Dropbox client with automatic token refresh"""
        try:
            self.dbx = dropbox.Dropbox(
                app_key=self.app_key,
                app_secret=self.app_secret,
                oauth2_refresh_token=self.refresh_token
            )
            # Test the connection
            self.dbx.users_get_current_account()
        except AuthError as e:
            logger.error(f"Authentication failed: {e}")
            raise ProcessingError(
                "Dropbox Authentication",
                "Invalid credentials. Please ensure your Dropbox refresh token is correct and not expired.",
                "Generate a new refresh token from the Dropbox App Console"
            )

    def list_folder_recursive(self, path: str) -> List[dropbox.files.FileMetadata]:
        """Recursively list all files in a Dropbox folder and its subfolders"""
        files = []
        try:
            result = self.dbx.files_list_folder(path, recursive=True)
            while True:
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        files.append(entry)
                if not result.has_more:
                    break
                result = self.dbx.files_list_folder_continue(result.cursor)
        except AuthError as e:
            logger.error(f"Authentication failed while listing folder {path}: {e}")
            raise ProcessingError(
                "Dropbox Authentication",
                "Authentication failed during folder listing. Please ensure your Dropbox refresh token is correct and not expired.",
                "Generate a new refresh token from the Dropbox App Console"
            )
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error listing folder {path}: {e}")
            raise ProcessingError(
                "Dropbox Access",
                str(e),
                "Check API key and permissions"
            )
        return files

    @backoff.on_exception(backoff.expo, DropboxException, max_tries=5)
    async def fetch_reports(self, config: Config) -> List[Tuple[str, io.BytesIO]]:
        """Fetch PDFs from Dropbox with recursive folder search"""
        pdf_files = []
        folder_path = config.get_dropbox_folder()
        logger.info(f"Fetching from Dropbox folder: {folder_path}")

        try:
            # Get all files recursively
            all_files = self.list_folder_recursive(folder_path)
            logger.debug(f"Found {len(all_files)} total files in folder '{folder_path}' and subfolders")

            # Filter for PDF files
            pdf_entries = [
                entry for entry in all_files
                if entry.name.lower().endswith('.pdf')
            ]
            logger.debug(f"Found {len(pdf_entries)} PDF files")

            # Download each PDF file
            for entry in pdf_entries:
                try:
                    logger.debug(f"Downloading file: {entry.name} from {entry.path_lower}")
                    _, res = self.dbx.files_download(entry.path_lower)
                    pdf_stream = io.BytesIO(res.content)
                    pdf_files.append((entry.name, pdf_stream))
                except AuthError as e:
                    logger.error(f"Authentication failed while downloading {entry.name}: {e}")
                    raise ProcessingError(
                        "Dropbox Authentication",
                        f"Authentication failed during downloading {entry.name}. Please ensure your Dropbox refresh token is correct and not expired.",
                        "Generate a new refresh token from the Dropbox App Console"
                    )
                except Exception as e:
                    logger.error(f"Error downloading {entry.name}: {e}")
                    continue

        except dropbox.exceptions.ApiError as api_err:
            if isinstance(api_err.error, dropbox.files.ListFolderError):
                logger.error(f"The folder '{folder_path}' does not exist.")
                raise ProcessingError(
                    "Dropbox Access",
                    f"The folder '{folder_path}' does not exist.",
                    "Verify the folder path and permissions"
                )
            else:
                raise ProcessingError(
                    "Dropbox Access",
                    str(api_err),
                    "Check API key and permissions"
                )

        logger.info(f"Successfully downloaded {len(pdf_files)} PDF files")
        return pdf_files

class OpenAIClient:
    """Handles OpenAI API calls with focus on accurate data extraction"""

    def __init__(self, api_key: str, http_proxy: str = None, https_proxy: str = None):
        """Initialize AsyncOpenAI client with optional proxy support"""
        # Configure proxy settings
        proxy_config = None
        if http_proxy or https_proxy:
            proxy_config = {"all://": http_proxy if http_proxy else https_proxy}
        
        # Initialize AsyncOpenAI with async http client
        self.client = AsyncOpenAI(
            api_key=api_key,
            http_client=httpx.AsyncClient(
                proxies=proxy_config,
                verify=True  # Enable SSL verification
            ) if proxy_config else None
        )

    def get_model_config(self, model: str) -> dict:
        """Get complete model configuration"""
        return MODEL_CONFIGS.get(model, MODEL_CONFIGS['gpt-4o-mini'])

    def create_initial_summary_prompt(self, file_name: str, content: str) -> str:
        """Create focused prompt for initial data extraction"""
        template = PROMPT_TEMPLATES['DATA_EXTRACTION']
        key_areas = "\n".join(f"{area}" for area in template['key_areas'])

        prompt = f"""{template['prefix']}

{key_areas}

Document: {file_name}

{template['format_instructions']}

Content:
{content}"""

        return prompt

    def create_batch_summary_prompt(self, content: str, token_count: int) -> str:
        """Create prompt for combining extracted data"""
        template = PROMPT_TEMPLATES['SYNTHESIS']
        key_areas = "\n".join(f"{area}" for area in template['key_areas'])

        prompt = f"""{template['prefix']}

{key_areas}

{template['format_instructions']}

Content:
{content}"""

        return prompt

    def create_final_summary_prompt(self, content: str) -> str:
        """Create prompt for final report generation"""
        template = PROMPT_TEMPLATES['FINAL_REPORT']
        sections = "\n".join(f"{section}" for section in template['key_sections'])

        prompt = f"""{template['prefix']}

{sections}

{template['format_instructions']}

Analysis Content:
{content}"""

        return prompt

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def generate_summary(self, prompt: str, model: str, max_tokens: int = None, max_completion_tokens: int = None) -> str:
        """Generate summary with retries and error handling"""
        try:
            # Get model configuration
            model_config = self.get_model_config(model)
            context_window = model_config['context_window']
            model_max_tokens = model_config['max_output_tokens']
            uses_completion_tokens = model_config['uses_completion_tokens']
            supports_temperature = model_config['supports_temperature']

            # Calculate prompt tokens
            prompt_tokens = get_token_count(prompt)

            # Validate prompt length
            if prompt_tokens >= context_window:
                raise ValueError(
                    f"Prompt length ({prompt_tokens} tokens) exceeds model's context window "
                    f"({context_window} tokens)"
                )

            # Calculate available tokens for response
            available_tokens = context_window - prompt_tokens

            # Determine max_tokens for response based on model type
            if uses_completion_tokens:
                # Models that specify completion tokens
                tokens_value = (max_completion_tokens if max_completion_tokens is not None
                                else min(model_max_tokens, available_tokens))
            else:
                # Models that specify max tokens directly
                tokens_value = (max_tokens if max_tokens is not None
                                else min(model_max_tokens, available_tokens))

            # Prepare parameters for the API call
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": tokens_value
            }

            # Add temperature only for models that support it
            if supports_temperature:
                params["temperature"] = 0.3

            # Make API call using AsyncOpenAI client
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content

        except Exception as e:
            error_msg = str(e)
            recovery_action = "Check API key and rate limits"

            if "context_length_exceeded" in error_msg:
                recovery_action = "Reduce input text or switch to a model with larger context window"
            elif "maximum_tokens" in error_msg:
                recovery_action = "Reduce requested max_tokens or switch to a model with larger output capacity"

            raise ProcessingError("OpenAI API", error_msg, recovery_action)
