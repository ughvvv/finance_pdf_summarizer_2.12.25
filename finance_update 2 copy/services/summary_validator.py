"""Service for validating summaries at different stages."""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import Counter

@dataclass
class ValidationResult:
    """Result of a summary validation."""
    is_valid: bool
    issues: List[str]
    stats: Dict  # Added statistics about the validation

class SummaryValidator:
    """Quality checks for financial summaries."""
    
    def __init__(self):
        """Initialize the validator."""
        # Financial data patterns to identify
        self.data_patterns = {
            'currency': r'\$\d+(?:\.\d+)?(?:k|m|b|bn|t|tn)?',
            'percentage': r'\d+(?:\.\d+)?%',
            'multiple': r'\d+(?:\.\d+)?x',
            'large_number': r'\d+(?:\.\d+)?\s*(?:million|billion|trillion)',
            'basis_points': r'\d+\s*(?:bps|basis\s+points?)',
            'growth_rate': r'(?:grew|increased|decreased|declined|fell|rose)\s+(?:by|to)?\s*\d+(?:\.\d+)?%?',
            'market_move': r'(?:up|down|higher|lower|above|below)\s+(?:by|to)?\s*\d+(?:\.\d+)?%?',
            'date': r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}|Q[1-4]|[12][0-9]{3}'
        }
        
        # Key financial concepts to check for
        self.key_concepts = [
            'revenue', 'earnings', 'growth', 'market', 'risk',
            'forecast', 'outlook', 'trend', 'performance'
        ]

        # Define market terms for analysis
        self.market_terms = [
            'revenue', 'profit', 'loss', 'margin', 'debt', 'equity',
            'asset', 'liability', 'cash flow', 'valuation'
        ]
        
    def validate_initial_summary(self, summary: str) -> ValidationResult:
        """Quality check for initial summary."""
        if not summary:
            return ValidationResult(False, ["Empty summary"], {'error': 'empty_summary'})
            
        suggestions = []
        stats = self._analyze_content(summary)
        
        # Check for presence of numerical data
        if stats['total_metrics'] < 3:
            suggestions.append("Consider including more quantitative data points")
            
        # Check for key financial concepts
        missing_concepts = [concept for concept in self.key_concepts 
                          if concept not in summary.lower()]
        if missing_concepts:
            suggestions.append(f"Consider addressing: {', '.join(missing_concepts)}")
            
        # Always return valid but with suggestions if needed
        return ValidationResult(True, suggestions, stats)
        
    def validate_topic_analysis(self, analysis: str) -> ValidationResult:
        """Quality check for topic analysis."""
        if not analysis:
            return ValidationResult(False, ["Empty analysis"], {'error': 'empty_analysis'})
            
        suggestions = []
        stats = self._analyze_content(analysis)
        
        # Check for trend discussion
        if not any(word in analysis.lower() for word in ['trend', 'pattern', 'movement']):
            suggestions.append("Consider discussing market trends")
            
        # Check for comparative analysis
        if not self._has_comparative_metrics(analysis):
            suggestions.append("Consider adding comparative metrics")
            
        return ValidationResult(True, suggestions, stats)
        
    def validate_final_analysis(self, analysis: str) -> ValidationResult:
        """Quality check for final analysis."""
        if not analysis:
            return ValidationResult(False, ["Empty analysis"], {'error': 'empty_analysis'})
            
        suggestions = []
        stats = self._analyze_content(analysis)
        
        # Check for forward-looking content
        if not any(word in analysis.lower() for word in ['outlook', 'forecast', 'expect']):
            suggestions.append("Consider including forward-looking analysis")
            
        # Check for risk discussion
        if not any(word in analysis.lower() for word in ['risk', 'challenge', 'concern']):
            suggestions.append("Consider addressing key risks")
            
        # Check for actionable insights
        if not any(word in analysis.lower() for word in ['recommend', 'suggest', 'should']):
            suggestions.append("Consider providing actionable recommendations")
                
        return ValidationResult(True, suggestions, stats)
        
    def _analyze_content(self, text: str) -> Dict:
        """Analyze content for metrics and patterns."""
        stats = {
            'total_metrics': 0,
            'metric_types': Counter(),
            'market_terms': Counter(),
            'sections': set()
        }
        
        # Count metric types
        for metric_type, pattern in self.data_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            count = sum(1 for _ in matches)
            stats['metric_types'][metric_type] = count
            stats['total_metrics'] += count
            
        # Count market terms
        for term in self.market_terms:
            stats['market_terms'][term] = len(re.findall(
                fr'\b{term}\b',
                text.lower()
            ))
            
        # Identify sections
        section_markers = ['metrics', 'analysis', 'risk', 'trends', 'impact', 'action']
        for marker in section_markers:
            if re.search(fr'\b{marker}\b', text.lower()):
                stats['sections'].add(marker)
                
        return stats
        
    def _check_sections(self, text: str, stage: str) -> List[str]:
        """Check for required sections."""
        text_lower = text.lower()
        return [
            section for section in self.required_sections[stage]
            if section not in text_lower
        ]
        
    def _check_metrics(self, text: str, stage: str) -> List[str]:
        """Check for required metric types."""
        stats = self._analyze_content(text)
        return [
            metric_type for metric_type in self.required_metrics[stage]
            if stats['metric_types'][metric_type] == 0
        ]
        
    def _check_market_terms(self, text: str) -> List[str]:
        """Check for market terms without associated metrics."""
        stats = self._analyze_content(text)
        return [
            term for term in self.market_terms
            if stats['market_terms'][term] > 0 and not self._term_has_metric(text, term)
        ]
        
    def _term_has_metric(self, text: str, term: str) -> bool:
        """Check if a market term has associated metrics."""
        # Look for occurrences of the term
        term_locations = [m.start() for m in re.finditer(fr'\b{term}\b', text.lower())]
        for loc in term_locations:
            # Check 100 characters before and after the term
            context = text[max(0, loc - 100):min(len(text), loc + 100)]
            if any(re.search(pattern, context, re.IGNORECASE) 
                   for pattern in self.data_patterns.values()):
                return True
        return False
        
    def _has_trend_analysis(self, text: str) -> bool:
        """Check for trend analysis with metrics."""
        trend_terms = ['trend', 'pattern', 'movement', 'shift', 'change']
        for term in trend_terms:
            if self._term_has_metric(text, term):
                return True
        return False
        
    def _has_comparative_metrics(self, text: str) -> bool:
        """Check for comparative metrics."""
        comparative_patterns = [
            r'compared to',
            r'versus',
            r'vs\.',
            r'higher than',
            r'lower than',
            r'increased from',
            r'decreased from'
        ]
        return any(
            re.search(f"{pattern}.*?{self.data_patterns['percentage']}", text, re.IGNORECASE)
            or re.search(f"{pattern}.*?{self.data_patterns['currency']}", text, re.IGNORECASE)
            for pattern in comparative_patterns
        )
        
    def _has_actionable_metrics(self, text: str) -> bool:
        """Check for actionable metrics."""
        action_terms = ['target', 'goal', 'objective', 'recommend', 'should']
        return any(self._term_has_metric(text, term) for term in action_terms)
        
    def _has_risk_quantification(self, text: str) -> bool:
        """Check for quantified risk metrics."""
        risk_terms = ['risk', 'exposure', 'probability', 'likelihood', 'impact']
        return any(self._term_has_metric(text, term) for term in risk_terms)
