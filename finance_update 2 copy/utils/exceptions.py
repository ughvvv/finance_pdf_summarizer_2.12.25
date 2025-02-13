"""Custom exceptions for the finance update project."""

from typing import Optional, Dict, Any, List

class FinanceUpdateError(Exception):
    """Base exception class for finance update project."""
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None
    ):
        super().__init__(message)
        self.details = details or {}
        self.recovery_action = recovery_action

class SummaryError(FinanceUpdateError):
    """Raised when there's an error in text summarization."""
    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        token_count: Optional[int] = None,
        chunk_info: Optional[Dict] = None,
        **kwargs
    ):
        details = {
            "model": model,
            "token_count": token_count,
            "chunk_info": chunk_info,
            **kwargs
        }
        super().__init__(message, details=details)

class ValidationError(FinanceUpdateError):
    """Raised when text validation fails."""
    def __init__(
        self,
        message: str,
        text_preview: Optional[str] = None,
        validation_rules: Optional[List[str]] = None,
        failed_rules: Optional[List[str]] = None,
        **kwargs
    ):
        details = {
            "text_preview": text_preview,
            "validation_rules": validation_rules,
            "failed_rules": failed_rules,
            **kwargs
        }
        super().__init__(message, details=details)

class ProcessingError(FinanceUpdateError):
    """Raised when batch processing encounters an error."""
    def __init__(
        self,
        message: str,
        batch_size: Optional[int] = None,
        processed_count: Optional[int] = None,
        failed_items: Optional[List[str]] = None,
        **kwargs
    ):
        details = {
            "batch_size": batch_size,
            "processed_count": processed_count,
            "failed_items": failed_items,
            **kwargs
        }
        super().__init__(message, details=details)

class PromptError(FinanceUpdateError):
    """Raised when there's an error with prompt templates."""
    def __init__(
        self,
        message: str,
        template_name: Optional[str] = None,
        template_version: Optional[str] = None,
        missing_variables: Optional[List[str]] = None,
        **kwargs
    ):
        details = {
            "template_name": template_name,
            "template_version": template_version,
            "missing_variables": missing_variables,
            **kwargs
        }
        super().__init__(message, details=details)

class ChunkError(FinanceUpdateError):
    """Raised when there's an error in text chunking."""
    def __init__(
        self,
        message: str,
        text_length: Optional[int] = None,
        chunk_size: Optional[int] = None,
        chunk_count: Optional[int] = None,
        **kwargs
    ):
        details = {
            "text_length": text_length,
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            **kwargs
        }
        super().__init__(message, details=details)

class MetricsError(FinanceUpdateError):
    """Raised when there's an error extracting metrics."""
    def __init__(
        self,
        message: str,
        metric_type: Optional[str] = None,
        source: Optional[str] = None,
        extraction_method: Optional[str] = None,
        **kwargs
    ):
        details = {
            "metric_type": metric_type,
            "source": source,
            "extraction_method": extraction_method,
            **kwargs
        }
        super().__init__(message, details=details)

class ExtractionError(FinanceUpdateError):
    """Raised when there's an error extracting text from documents."""
    def __init__(
        self,
        message: str,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        extraction_method: Optional[str] = None,
        error_details: Optional[str] = None,
        **kwargs
    ):
        details = {
            "file_name": file_name,
            "file_type": file_type,
            "extraction_method": extraction_method,
            "error_details": error_details,
            **kwargs
        }
        super().__init__(message, details=details)

class NotificationError(FinanceUpdateError):
    """Raised when there's an error sending notifications."""
    def __init__(
        self,
        message: str,
        notification_type: Optional[str] = None,
        recipient: Optional[str] = None,
        service_error: Optional[str] = None,
        **kwargs
    ):
        details = {
            "notification_type": notification_type,
            "recipient": recipient,
            "service_error": service_error,
            **kwargs
        }
        super().__init__(message, details=details)

class ConfigurationError(FinanceUpdateError):
    """Raised when there's an error in configuration."""
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None,
        **kwargs
    ):
        details = {
            "config_key": config_key,
            "expected_type": expected_type,
            "actual_value": actual_value,
            **kwargs
        }
        super().__init__(message, details=details)

def create_error_report(error: FinanceUpdateError) -> Dict[str, Any]:
    """Create a detailed error report from an exception."""
    return {
        "error_type": error.__class__.__name__,
        "message": str(error),
        "details": error.details,
        "recovery_action": error.recovery_action,
        "traceback": getattr(error, "__traceback__", None)
    }

def suggest_recovery_action(error: FinanceUpdateError) -> str:
    """Suggest recovery actions based on error type and details."""
    if isinstance(error, SummaryError):
        if error.details.get("token_count", 0) > error.details.get("max_tokens", 0):
            return "Try reducing the input text size or increasing the maximum token limit"
        return "Check the model configuration and try again with different parameters"
    
    elif isinstance(error, ValidationError):
        failed_rules = error.details.get("failed_rules", [])
        if failed_rules:
            return f"Fix the following validation issues: {', '.join(failed_rules)}"
        return "Review the text content and ensure it meets validation requirements"
    
    elif isinstance(error, ProcessingError):
        failed_count = len(error.details.get("failed_items", []))
        if failed_count > 0:
            return f"Retry processing for {failed_count} failed items"
        return "Check system resources and try processing with a smaller batch size"
    
    elif isinstance(error, PromptError):
        if error.details.get("missing_variables"):
            return f"Provide values for missing variables: {error.details['missing_variables']}"
        return "Check template configuration and ensure all required variables are defined"
    
    elif isinstance(error, ChunkError):
        if error.details.get("text_length", 0) > error.details.get("chunk_size", 0):
            return "Try increasing the chunk size or using a different chunking strategy"
        return "Review chunking parameters and adjust based on text characteristics"
    
    elif isinstance(error, MetricsError):
        return f"Check the source data for metric type '{error.details.get('metric_type')}' and try again"
    
    elif isinstance(error, ExtractionError):
        return f"Check the file '{error.details.get('file_name')}' and extraction method '{error.details.get('extraction_method')}' for errors"
    
    elif isinstance(error, ConfigurationError):
        return f"Update configuration value for '{error.details.get('config_key')}' to match expected type"
    
    return "Contact system administrator for assistance"
