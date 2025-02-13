"""Service for extracting and analyzing financial metrics from text."""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MetricMatch:
    """Represents a matched metric with context."""
    metric_type: str
    value: str
    context: str
    confidence: float

class MetricsExtractor:
    """Handles extraction and analysis of financial metrics from text."""

    def __init__(self):
        # Core financial metrics patterns
        self.currency_pattern = r'\$\d+(?:\.\d+)?(?:k|m|b|bn|t|tn)?'
        self.percentage_pattern = r'\d+(?:\.\d+)?%'
        self.multiple_pattern = r'\d+(?:\.\d+)?x'
        self.large_number_pattern = r'\d+(?:\.\d+)?\s*(?:million|billion|trillion)'
        self.basis_points_pattern = r'\d+\s*(?:bps|basis\s+points?)'
        
        # Key financial terms to track
        self.key_metrics = {
            'revenue': ['revenue', 'sales', 'turnover'],
            'earnings': ['earnings', 'profit', 'income', 'ebitda', 'net income'],
            'margins': ['margin', 'profitability', 'markup'],
            'growth': ['growth', 'increase', 'expansion'],
            'market': ['market share', 'market cap', 'valuation'],
            'performance': ['performance', 'results', 'achievement']
        }
        
        # Context window size for metric extraction
        self.context_window = 100  # characters

    def extract_metrics(self, text: str) -> Dict[str, List[MetricMatch]]:
        """
        Extract all financial metrics from text with context.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary mapping metric types to lists of MetricMatch objects
        """
        metrics = {}
        
        # Extract currency amounts
        metrics['currency'] = self._find_matches(text, self.currency_pattern)
        
        # Extract percentages
        metrics['percentage'] = self._find_matches(text, self.percentage_pattern)
        
        # Extract multiples
        metrics['multiple'] = self._find_matches(text, self.multiple_pattern)
        
        # Extract large numbers
        metrics['large_number'] = self._find_matches(text, self.large_number_pattern)
        
        # Extract basis points
        metrics['basis_points'] = self._find_matches(text, self.basis_points_pattern)
        
        # Extract key metric mentions
        for metric_type, terms in self.key_metrics.items():
            pattern = self._build_metric_pattern(terms)
            metrics[metric_type] = self._find_matches(text, pattern)
            
        return metrics

    def compare_metrics(
        self,
        original_metrics: Dict[str, List[MetricMatch]],
        summary_metrics: Dict[str, List[MetricMatch]]
    ) -> Tuple[float, List[str]]:
        """
        Compare metrics between original text and summary.
        
        Args:
            original_metrics: Metrics from original text
            summary_metrics: Metrics from summary
            
        Returns:
            Tuple of (preservation_ratio, list of missing important metrics)
        """
        missing_metrics = []
        preserved_count = 0
        total_count = 0
        
        for metric_type, original_matches in original_metrics.items():
            for original_match in original_matches:
                total_count += 1
                if self._find_matching_metric(original_match, summary_metrics.get(metric_type, [])):
                    preserved_count += 1
                else:
                    missing_metrics.append(
                        f"{metric_type}: {original_match.value} ({original_match.context})"
                    )
        
        preservation_ratio = preserved_count / total_count if total_count > 0 else 1.0
        return preservation_ratio, missing_metrics

    def get_key_insights(self, metrics: Dict[str, List[MetricMatch]], limit: int = 5) -> List[str]:
        """
        Extract key financial insights from metrics.
        
        Args:
            metrics: Extracted metrics
            limit: Maximum number of insights to return
            
        Returns:
            List of key insights as strings
        """
        insights = []
        
        # Prioritize metrics by confidence
        all_matches = []
        for metric_type, matches in metrics.items():
            all_matches.extend(matches)
        
        # Sort by confidence and take top matches
        top_matches = sorted(
            all_matches,
            key=lambda x: x.confidence,
            reverse=True
        )[:limit]
        
        # Format insights
        for match in top_matches:
            insight = f"{match.metric_type.title()}: {match.value}"
            if match.context:
                insight += f" ({match.context})"
            insights.append(insight)
            
        return insights

    def _find_matches(self, text: str, pattern: str) -> List[MetricMatch]:
        """Find all matches for a pattern with surrounding context."""
        matches = []
        
        for match in re.finditer(pattern, text):
            value = match.group(0)
            start_pos = max(0, match.start() - self.context_window)
            end_pos = min(len(text), match.end() + self.context_window)
            
            # Extract context before and after match
            context = text[start_pos:end_pos].strip()
            
            # Calculate confidence based on context quality
            confidence = self._calculate_confidence(value, context)
            
            matches.append(MetricMatch(
                metric_type=pattern,
                value=value,
                context=context,
                confidence=confidence
            ))
            
        return matches

    def _build_metric_pattern(self, terms: List[str]) -> str:
        """Build regex pattern for key metric terms."""
        escaped_terms = [re.escape(term) for term in terms]
        return fr'(?i)(?:{"|".join(escaped_terms)})\s*(?::|of|at|is|was|=)?\s*([^.]*)'

    def _calculate_confidence(self, value: str, context: str) -> float:
        """Calculate confidence score for a metric match."""
        confidence = 1.0
        
        # Reduce confidence for matches without clear context
        if len(context.split()) < 5:
            confidence *= 0.8
            
        # Boost confidence for matches with supporting terms
        supporting_terms = {
            'increased', 'decreased', 'grew', 'declined', 'reached',
            'approximately', 'estimated', 'reported', 'projected'
        }
        if any(term in context.lower() for term in supporting_terms):
            confidence *= 1.2
            
        # Cap confidence at 1.0
        return min(confidence, 1.0)

    def _find_matching_metric(self, original: MetricMatch, candidates: List[MetricMatch]) -> bool:
        """Find if a matching metric exists in candidates."""
        for candidate in candidates:
            # Compare numerical values with tolerance
            if self._similar_values(original.value, candidate.value):
                return True
        return False

    def _similar_values(self, val1: str, val2: str) -> bool:
        """Check if two metric values are similar (accounting for formatting differences)."""
        # Clean and normalize values
        val1 = re.sub(r'[^\d.%$kmbt]', '', val1.lower())
        val2 = re.sub(r'[^\d.%$kmbt]', '', val2.lower())
        
        # Extract numbers
        num1 = re.findall(r'\d+(?:\.\d+)?', val1)
        num2 = re.findall(r'\d+(?:\.\d+)?', val2)
        
        if not num1 or not num2:
            return False
            
        # Compare numbers with tolerance
        try:
            return abs(float(num1[0]) - float(num2[0])) < 0.01
        except ValueError:
            return False
