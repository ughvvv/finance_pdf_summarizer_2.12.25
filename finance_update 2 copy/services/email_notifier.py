"""Service for sending email notifications with analysis results."""

import logging
from typing import Optional
from utils.email_handler import EmailSender
from utils.exceptions import NotificationError

logger = logging.getLogger(__name__)

class EmailNotifier:
    """Handles sending email notifications with analysis results."""
    
    def __init__(self, email_sender: EmailSender):
        """
        Initialize EmailNotifier.
        
        Args:
            email_sender: Initialized email sender
        """
        self.email_sender = email_sender
        
    async def send_analysis(self, analysis: str, subject: Optional[str] = None) -> None:
        """
        Send analysis results via email.
        
        Args:
            analysis: Analysis content to send
            subject: Optional custom subject line
            
        Raises:
            NotificationError: If sending email fails
        """
        try:
            logger.info("Sending analysis email")
            await self.email_sender.send_analysis_email(
                analysis,
                subject=subject or "Financial Report Analysis"
            )
            logger.info("Email sent successfully")
        except Exception as e:
            logger.error(f"Error sending analysis email: {e}", exc_info=True)
            raise NotificationError(f"Failed to send email: {str(e)}")
