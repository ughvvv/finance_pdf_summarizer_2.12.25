"""Service for storing and retrieving analysis reports."""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AnalysisStore:
    """Handles storing and retrieving analysis reports."""
    
    def __init__(self, base_dir: str = "analysis_archive"):
        """
        Initialize AnalysisStore.
        
        Args:
            base_dir: Base directory for storing analysis files
        """
        self.base_dir = base_dir
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self):
        """Ensure the storage directory exists."""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            logger.info(f"Created analysis archive directory: {self.base_dir}")
    
    def store_analysis(self, analysis_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store an analysis report with metadata.
        
        Args:
            analysis_data: The analysis content to store
            metadata: Additional metadata about the analysis
            
        Returns:
            Path to the stored analysis file
        """
        # Create timestamp-based directory structure
        now = datetime.now()
        year_dir = os.path.join(self.base_dir, str(now.year))
        month_dir = os.path.join(year_dir, now.strftime("%m-%B"))
        day_dir = os.path.join(month_dir, now.strftime("%d"))
        
        # Ensure directories exist
        for dir_path in [year_dir, month_dir, day_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        
        # Prepare the complete data structure
        full_data = {
            "timestamp": now.isoformat(),
            "analysis": analysis_data,
            "metadata": metadata or {},
            "source_files": [],  # List of processed files
            "processing_stats": {
                "num_files": 0,
                "processing_time": 0,
                "token_count": 0
            }
        }
        
        # Generate filename with timestamp
        filename = f"analysis_{now.strftime('%Y%m%d_%H%M%S')}.json"
        file_path = os.path.join(day_dir, filename)
        
        # Store the analysis
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Stored analysis report: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error storing analysis: {e}")
            raise
    
    def get_latest_analysis(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recent analysis report.
        
        Returns:
            The most recent analysis data or None if not found
        """
        try:
            # Find the most recent year
            years = sorted([d for d in os.listdir(self.base_dir) 
                          if os.path.isdir(os.path.join(self.base_dir, d))], reverse=True)
            if not years:
                return None
            
            year_dir = os.path.join(self.base_dir, years[0])
            
            # Find the most recent month
            months = sorted([d for d in os.listdir(year_dir) 
                           if os.path.isdir(os.path.join(year_dir, d))], reverse=True)
            if not months:
                return None
            
            month_dir = os.path.join(year_dir, months[0])
            
            # Find the most recent day
            days = sorted([d for d in os.listdir(month_dir) 
                         if os.path.isdir(os.path.join(month_dir, d))], reverse=True)
            if not days:
                return None
            
            day_dir = os.path.join(month_dir, days[0])
            
            # Find the most recent analysis file
            files = sorted([f for f in os.listdir(day_dir) 
                          if f.endswith('.json')], reverse=True)
            if not files:
                return None
            
            file_path = os.path.join(day_dir, files[0])
            
            # Load and return the analysis
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error retrieving latest analysis: {e}")
            return None
    
    def get_analysis_by_date(self, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Retrieve an analysis report for a specific date.
        
        Args:
            date: The date to retrieve the analysis for
            
        Returns:
            The analysis data or None if not found
        """
        try:
            # Construct the path for the specified date
            path = os.path.join(
                self.base_dir,
                str(date.year),
                date.strftime("%m-%B"),
                date.strftime("%d")
            )
            
            if not os.path.exists(path):
                return None
            
            # Find all analysis files for that date
            files = sorted([f for f in os.listdir(path) 
                          if f.endswith('.json')], reverse=True)
            if not files:
                return None
            
            # Load and return the most recent analysis for that date
            file_path = os.path.join(path, files[0])
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error retrieving analysis for date {date}: {e}")
            return None
