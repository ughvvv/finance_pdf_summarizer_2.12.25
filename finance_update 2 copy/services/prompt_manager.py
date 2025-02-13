"""Service for managing and optimizing prompt templates."""

import logging
import json
from typing import Dict, Optional, List
from dataclasses import dataclass
import random
from datetime import datetime

from utils.text_processor import get_token_count

logger = logging.getLogger(__name__)

@dataclass
class PromptTemplate:
    """Template for generating prompts."""
    name: str
    template: str
    version: str
    description: str
    max_tokens: int
    created_at: str = datetime.now().isoformat()
    variables: List[str] = None
    examples: List[Dict] = None
    
    @property
    def base_token_count(self) -> int:
        """Calculate base token count without variables."""
        return get_token_count(self.template)

class PromptVariant:
    """Variant of a prompt template for A/B testing."""
    def __init__(
        self,
        template: PromptTemplate,
        variant_id: str,
        weight: float = 1.0
    ):
        self.template = template
        self.variant_id = variant_id
        self.weight = weight
        self.uses = 0
        self.successes = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of this variant."""
        return (self.successes / self.uses) * 100 if self.uses > 0 else 0
    
    def record_use(self, success: bool):
        """Record usage of this variant."""
        self.uses += 1
        if success:
            self.successes += 1

class PromptManager:
    """Manages prompt templates and their optimization."""
    
    # Default templates for different summarization stages
    DEFAULT_TEMPLATES = {
        "initial_summary": PromptTemplate(
            name="initial_summary",
            template=(
                "Context:\n"
                "You are provided with a series of individual investment bank report summaries. Each summary covers "
                "macroeconomic trends, sector-specific insights, risk warnings, and investment opportunities. Your task is to "
                "generate a concise, robust summary for each report individually.\n\n"
                "Role:\n"
                "Act as a senior investment strategist with deep expertise in financial research and portfolio management.\n\n"
                "Instructions:\n"
                "For each individual report summary, please produce a structured summary that includes the following sections:\n\n"
                "1. Executive Summary:\n"
                "   - Provide a brief overview of the report's core thesis and main themes.\n"
                "   - Summarize the primary narrative (e.g., shifts in monetary policy, sector performance, trade/tariff impacts).\n\n"
                "2. Key Data Points:\n"
                "   - List the most critical quantitative metrics and statistics mentioned (e.g., earnings growth, inflation rates, yield levels).\n"
                "   - Include any significant comparative figures (e.g., historical averages, consensus estimates).\n\n"
                "3. Risks and Uncertainties:\n"
                "   - Identify and briefly explain the major risks or uncertainties noted in the report (e.g., regulatory challenges, geopolitical tensions, data discrepancies).\n"
                "   - Note any conflicts or areas where reports differ in outlook.\n\n"
                "4. Actionable Investment Implications:\n"
                "   - Summarize the recommended portfolio adjustments or trading strategies (e.g., sector rotations, hedging strategies, specific asset plays).\n"
                "   - Highlight key triggers or catalysts to monitor (e.g., upcoming earnings, central bank meetings).\n\n"
                "5. Additional Insights (Optional):\n"
                "   - Note any contrarian viewpoints or unique perspectives that challenge conventional wisdom.\n"
                "   - Include any relevant context about market sentiment or future projections.\n\n"
                "Formatting Requirements:\n"
                "- Use clear headings for each section and bullet points where appropriate.\n"
                "- Keep language concise and avoid unnecessary jargon; if technical terms are used, include brief explanations.\n"
                "- Each report summary should be self-contained and provide a clear, actionable overview for a senior investment strategist.\n\n"
                "Output:\n"
                "Process each individual report summary separately and output a numbered list where each item corresponds to a robust summary of one report. "
                "Ensure that your output is logically organized and provides actionable insights for portfolio management.\n\n"
                "Example Format:\n"
                "Report Summary #1:\n"
                "Executive Summary:\n"
                " - [Brief overview of main thesis and themes]\n"
                "Key Data Points:\n"
                " - [Data Point 1: description and figure]\n"
                " - [Data Point 2: description and figure]\n"
                "Risks and Uncertainties:\n"
                " - [Risk 1: description]\n"
                " - [Uncertainty: description]\n"
                "Actionable Investment Implications:\n"
                " - [Suggested portfolio adjustment or trading idea]\n"
                " - [Key monitoring trigger]\n"
                "Additional Insights:\n"
                " - [Optional contrarian views or context]\n\n"
                "Document to summarize:\n{text}"
            ),
            version="1.1",
            description="Improved template for initial text summarization with detailed structure for actionable investment insights",
            max_tokens=8000,
            variables=["text"]
        ),
        "group_summary": PromptTemplate(
            name="group_summary",
            template=(
                "Synthesize the following summaries into a comprehensive market narrative that preserves key insights while identifying patterns and themes. "
                "Focus on both the quantitative and qualitative aspects:\n\n"
                "1. NARRATIVE SYNTHESIS:\n"
                "- Identify common themes and patterns:\n"
                "  * Recurring arguments and viewpoints\n"
                "  * Areas of consensus and disagreement\n"
                "  * Evolution of key debates\n"
                "- Capture unique perspectives:\n"
                "  * Non-consensus views\n"
                "  * Contrarian arguments\n"
                "  * Novel insights\n"
                "- Note changes in sentiment:\n"
                "  * Shifts in analyst positioning\n"
                "  * Evolution of market views\n"
                "  * Emerging narratives\n\n"
                "2. DATA SYNTHESIS:\n"
                "- Aggregate and analyze metrics:\n"
                "  * Compare and contrast data points\n"
                "  * Identify trends and patterns\n"
                "  * Note significant changes\n"
                "- Market indicators:\n"
                "  * Price and volume trends\n"
                "  * Positioning data\n"
                "  * Technical levels\n"
                "- Industry metrics:\n"
                "  * Sector performance\n"
                "  * Competitive dynamics\n"
                "  * Market share shifts\n\n"
                "3. INVESTMENT IMPLICATIONS:\n"
                "- Trading opportunities:\n"
                "  * High-conviction ideas\n"
                "  * Risk/reward scenarios\n"
                "  * Implementation strategies\n"
                "- Risk factors:\n"
                "  * Common concerns\n"
                "  * Potential catalysts\n"
                "  * Hedging approaches\n"
                "- Timeline considerations:\n"
                "  * Key events and dates\n"
                "  * Monitoring points\n"
                "  * Action triggers\n\n"
                "Format the output in a clear, structured format with the following sections:\n\n"
                "# MARKET NARRATIVE\n"
                "- Key themes and patterns\n"
                "- Areas of consensus/disagreement\n"
                "- Sentiment evolution\n\n"
                "# DATA SYNTHESIS\n"
                "- Aggregated metrics\n"
                "- Market indicators\n"
                "- Industry trends\n\n"
                "# INVESTMENT IMPLICATIONS\n"
                "- Trading opportunities\n"
                "- Risk considerations\n"
                "- Timeline factors\n\n"
                "Summaries to synthesize:\n{text}"
            ),
            version="1.0",
            description="Template for combining summaries with focus on narrative synthesis",
            max_tokens=8000,
            variables=["text"]
        ),
        "final_analysis": PromptTemplate(
            name="final_analysis",
            template=(
                "Create a comprehensive financial analysis that synthesizes the latest market updates and data, designed to provide clarity on key themes, regions, sectors, and actionable investment ideas.\n\n"
                "# MARKET NARRATIVE\n"
                "A. Key Themes and Debates Driving Markets\n"
                "B. Competing Viewpoints and Their Rationale\n"
                "C. Evolution of Market Sentiment\n"
                "D. Areas of Consensus and Disagreement\n\n"
                "# REGIONAL/SECTOR ANALYSIS\n"
                "A. U.S. and Developed Economies\n"
                "- Dominant Narrative\n"
                "- Supporting Indicators\n"
                "- Dynamics\n"
                "- Forward Looking\n\n"
                "B. Emerging Markets\n"
                "- Dominant Narrative\n"
                "- Supporting Indicators\n"
                "- Dynamics\n"
                "- Forward Looking\n\n"
                "C. Sector Focus\n"
                "- Dominant Narrative\n"
                "- Supporting Indicators\n"
                "- Dynamics\n"
                "- Forward Looking\n\n"
                "# INVESTMENT OPPORTUNITIES\n"
                "A. Core Investment Ideas\n"
                "[For each idea provide]\n"
                "1. Investment Thesis\n"
                "2. Company/Asset Context\n"
                "3. Supporting Metrics\n"
                "4. Catalyst Timeline\n"
                "5. Bull Case\n"
                "6. Risk Assessment\n\n"
                "B. Contrarian Ideas\n"
                "[For each idea include]\n"
                "1. Why It's Contrarian\n"
                "2. Supporting Evidence\n"
                "3. Potential Payoff\n"
                "4. Entry Strategy\n\n"
                "C. Additional Non-Obvious Stock Picks\n"
                "- Emerging Market Candidates\n"
                "- Innovative Disruptors\n"
                "- Micro-Cap Undervalued Securities\n\n"
                "# MARKET SIGNIFICANCE\n"
                "A. Short-Term Implications\n"
                "B. Medium-Term Outlook\n"
                "C. Sector Rotation Analysis\n\n"
                "# ACTIONABLE RECOMMENDATIONS\n"
                "A. Specific Trade Ideas with Entry Points\n"
                "B. Risk Management Guidelines\n"
                "C. Timeline Considerations\n\n"
                "# SYNTHESIS\n"
                "A. Most Compelling Arguments\n"
                "B. Areas of Highest Conviction\n"
                "C. Key Debates to Monitor\n"
                "D. Critical Uncertainties\n"
                "E. Suggested Action Items\n\n"
                "Input data to analyze:\n{text}"
            ),
            version="1.0",
            description="Template for generating final analysis with enhanced narrative focus",
            max_tokens=32000,
            variables=["text"]
        )
    }

    def __init__(self, templates_path: Optional[str] = None):
        """
        Initialize PromptManager.
        
        Args:
            templates_path: Optional path to JSON file with custom templates
        """
        self.templates = self.DEFAULT_TEMPLATES.copy()
        self.variants: Dict[str, List[PromptVariant]] = {}
        
        if templates_path:
            self.load_templates(templates_path)
        
        # Initialize variants for A/B testing
        self._initialize_variants()

    def load_templates(self, path: str):
        """Load templates from JSON file."""
        try:
            with open(path, 'r') as f:
                custom_templates = json.load(f)
            
            for name, data in custom_templates.items():
                template = PromptTemplate(**data)
                self.templates[name] = template
                logger.info(f"Loaded custom template: {name} (v{template.version})")
                
        except Exception as e:
            logger.error(f"Error loading templates from {path}: {e}")
            raise

    def _initialize_variants(self):
        """Initialize variants for A/B testing."""
        # Example: Create variants for initial summary template
        initial_variants = [
            (
                "standard",
                self.templates["initial_summary"],
                1.0
            ),
            (
                "detailed",
                PromptTemplate(
                    name="initial_summary_detailed",
                    template=(
                        "Create a comprehensive summary that prioritizes analyst insights and narrative while preserving key data.\n\n"
                        "Focus on extracting:\n"
                        "1. ANALYST NARRATIVE\n"
                        "- Main arguments and reasoning\n"
                        "- Level of conviction and confidence\n"
                        "- Unique perspectives and predictions\n"
                        "- Areas of uncertainty or concern\n\n"
                        "2. MARKET CONTEXT\n"
                        "- Current market environment\n"
                        "- Industry/sector dynamics\n"
                        "- Competitive landscape\n\n"
                        "3. SUPPORTING DATA\n"
                        "- Key metrics with context\n"
                        "- Market indicators\n"
                        "- Industry KPIs\n\n"
                        "4. INVESTMENT IMPLICATIONS\n"
                        "- Trading opportunities\n"
                        "- Risk considerations\n"
                        "- Timeline factors\n\n"
                        "{text}"
                    ),
                    version="1.0",
                    description="Detailed variant focusing on analyst narrative",
                    max_tokens=8000,
                    variables=["text"]
                ),
                0.5
            ),
            (
                "concise",
                PromptTemplate(
                    name="initial_summary_concise",
                    template=(
                        "Create a focused summary that captures the key analyst insights and supporting evidence.\n\n"
                        "Extract and analyze:\n"
                        "1. MAIN NARRATIVE\n"
                        "- Core thesis and arguments\n"
                        "- Unique perspectives\n"
                        "- Key uncertainties\n\n"
                        "2. SUPPORTING EVIDENCE\n"
                        "- Critical metrics\n"
                        "- Market context\n"
                        "- Industry dynamics\n\n"
                        "3. IMPLICATIONS\n"
                        "- Investment opportunities\n"
                        "- Risk factors\n"
                        "- Action points\n\n"
                        "{text}"
                    ),
                    version="1.0",
                    description="Concise variant focusing on key insights",
                    max_tokens=8000,
                    variables=["text"]
                ),
                0.5
            )
        ]
        
        self.variants["initial_summary"] = [
            PromptVariant(template, variant_id, weight)
            for variant_id, template, weight in initial_variants
        ]

    def get_template(
        self,
        name: str,
        enable_variants: bool = False
    ) -> PromptTemplate:
        """
        Get a prompt template, optionally selecting from variants.
        
        Args:
            name: Name of the template
            enable_variants: Whether to enable A/B testing variants
            
        Returns:
            Selected template
        """
        if name not in self.templates:
            raise ValueError(f"Template not found: {name}")
            
        if enable_variants and name in self.variants:
            # Select variant based on weights
            variants = self.variants[name]
            weights = [v.weight for v in variants]
            variant = random.choices(variants, weights=weights)[0]
            logger.info(
                f"Selected variant {variant.variant_id} for template {name}"
            )
            return variant.template
            
        return self.templates[name]

    def format_prompt(
        self,
        name: str,
        variables: Dict[str, str],
        enable_variants: bool = False,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Format a prompt template with variables.
        
        Args:
            name: Name of the template
            variables: Dictionary of variables to format template with
            enable_variants: Whether to enable A/B testing variants
            max_tokens: Optional maximum tokens for output (output control only)
            
        Returns:
            Formatted prompt
        """
        template = self.get_template(name, enable_variants)
        
        # Validate variables
        if template.variables:
            missing = set(template.variables) - set(variables.keys())
            if missing:
                raise ValueError(
                    f"Missing required variables for template {name}: {missing}"
                )
        
        # Format and return the prompt without truncating the input text
        prompt = template.template.format(**variables)
        return prompt

    def record_variant_result(
        self,
        name: str,
        variant_id: str,
        success: bool
    ):
        """Record result of using a prompt variant."""
        if name in self.variants:
            for variant in self.variants[name]:
                if variant.variant_id == variant_id:
                    variant.record_use(success)
                    logger.info(
                        f"Recorded {success} result for variant {variant_id} "
                        f"of template {name} (success rate: {variant.success_rate:.1f}%)"
                    )
                    break

    def get_variant_stats(self, name: str) -> List[Dict]:
        """Get statistics for variants of a template."""
        if name not in self.variants:
            return []
            
        return [
            {
                "variant_id": v.variant_id,
                "uses": v.uses,
                "successes": v.successes,
                "success_rate": v.success_rate,
                "weight": v.weight
            }
            for v in self.variants[name]
        ]

    def optimize_weights(self, name: str):
        """Optimize weights for variants based on performance."""
        if name not in self.variants:
            return
            
        variants = self.variants[name]
        total_uses = sum(v.uses for v in variants)
        
        if total_uses < 100:  # Need minimum sample size
            return
            
        # Calculate new weights based on success rates
        rates = [v.success_rate for v in variants]
        total_rate = sum(rates)
        
        if total_rate > 0:
            for variant, rate in zip(variants, rates):
                # Update weight while maintaining some exploration
                variant.weight = 0.1 + (0.9 * rate / total_rate)
                logger.info(
                    f"Updated weight for variant {variant.variant_id} "
                    f"of template {name} to {variant.weight:.2f}"
                )
