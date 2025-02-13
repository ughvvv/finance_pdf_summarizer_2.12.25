"""Service for analyzing topics in financial summaries."""

import logging
from typing import Dict, List
from clients.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class TopicAnalyzer:
    """Analyzes topics in financial summaries."""
    
    def __init__(self, openai_client: OpenAIClient, model: str = 'gpt-4o-mini'):
        """
        Initialize TopicAnalyzer.
        
        Args:
            openai_client: OpenAI client instance
            model: Model to use for analysis (default: gpt-4o-mini)
        """
        self.openai_client = openai_client
        self.model = model
        self.topics = [
            "Financial Performance",
            "Market Position",
            "Risk Analysis",
            "Strategic Initiatives",
            "Operational Efficiency",
            "Growth Trajectory"
        ]
        
    async def analyze_summary(self, summary: str) -> Dict[str, str]:
        """
        Analyze a summary and break it down by topics.
        
        Args:
            summary: Text to analyze
            
        Returns:
            Dictionary mapping topics to their analyses
        """
        analyses = {}
        
        for topic in self.topics:
            prompt = self._create_topic_prompt(topic, summary)
            analysis = await self.openai_client.generate_summary(
                prompt=prompt,
                model=self.model,
                max_tokens=10000
            )
            if analysis:
                analyses[topic] = analysis
            
        return analyses
        
    def _create_topic_prompt(self, topic: str, summary: str) -> str:
        """Create a prompt for analyzing a specific topic."""
        prompts = {
            "Financial Performance": """
                Conduct a deep-dive analysis of financial performance metrics. Focus on:

                1. Revenue Analysis:
                   - Growth rates and trends
                   - Revenue composition
                   - Geographic distribution
                   - Product/service mix
                   - Customer segment contribution

                2. Profitability Metrics:
                   - Margin analysis (gross, operating, net)
                   - Cost structure evolution
                   - Efficiency ratios
                   - Return metrics (ROE, ROA, ROIC)
                   - Working capital efficiency

                3. Cash Flow Dynamics:
                   - Operating cash flow trends
                   - Investment patterns
                   - Financing activities
                   - Cash conversion cycle
                   - Liquidity metrics

                4. Balance Sheet Health:
                   - Asset utilization
                   - Liability management
                   - Capital structure
                   - Investment efficiency
                   - Risk exposure

                Required Output Structure:
                - Key Metrics Analysis
                - Performance Drivers
                - Efficiency Indicators
                - Risk Factors
                - Forward Indicators
                """,
                
            "Market Position": """
                Analyze market position and competitive dynamics in detail. Focus on:

                1. Market Share Analysis:
                   - Overall market position
                   - Segment-specific share
                   - Share trends and momentum
                   - Competitive gains/losses
                   - Market concentration

                2. Competitive Landscape:
                   - Competitor mapping
                   - Strength/weakness analysis
                   - Competitive advantages
                   - Threat assessment
                   - Market power dynamics

                3. Geographic Presence:
                   - Regional performance
                   - Market penetration
                   - Growth opportunities
                   - Regional risks
                   - Expansion potential

                4. Customer Analysis:
                   - Customer segments
                   - Behavior patterns
                   - Loyalty metrics
                   - Acquisition costs
                   - Lifetime value trends

                Required Output Structure:
                - Market Share Assessment
                - Competitive Position
                - Geographic Strategy
                - Customer Intelligence
                - Strategic Implications
                """,
                
            "Risk Analysis": """
                Perform comprehensive risk assessment. Focus on:

                1. Market Risks:
                   - Demand volatility
                   - Pricing pressure
                   - Competitive threats
                   - Market saturation
                   - Disruption potential

                2. Operational Risks:
                   - Supply chain vulnerability
                   - Resource constraints
                   - Quality issues
                   - Process inefficiencies
                   - Capacity limitations

                3. Financial Risks:
                   - Credit exposure
                   - Currency risk
                   - Liquidity concerns
                   - Capital structure
                   - Investment risk

                4. Strategic Risks:
                   - Technology disruption
                   - Regulatory changes
                   - Market shifts
                   - Innovation gaps
                   - Execution risks

                Required Output Structure:
                - Risk Identification
                - Impact Assessment
                - Probability Analysis
                - Mitigation Strategies
                - Monitoring Framework
                """,
                
            "Strategic Initiatives": """
                Analyze strategic initiatives and execution plans. Focus on:

                1. Growth Strategy:
                   - Organic growth plans
                   - M&A opportunities
                   - Market expansion
                   - Product development
                   - Customer acquisition

                2. Innovation Pipeline:
                   - R&D investments
                   - Product roadmap
                   - Technology adoption
                   - Innovation metrics
                   - Competitive positioning

                3. Operational Excellence:
                   - Process improvement
                   - Cost optimization
                   - Quality enhancement
                   - Efficiency gains
                   - Productivity metrics

                4. Market Development:
                   - New market entry
                   - Channel expansion
                   - Partnership strategy
                   - Brand development
                   - Customer engagement

                Required Output Structure:
                - Strategic Priorities
                - Resource Requirements
                - Timeline Planning
                - Success Metrics
                - Risk Mitigation
                """,
                
            "Operational Efficiency": """
                Analyze operational performance and efficiency metrics. Focus on:

                1. Process Efficiency:
                   - Throughput metrics
                   - Cycle times
                   - Resource utilization
                   - Quality metrics
                   - Cost per unit

                2. Resource Management:
                   - Capacity utilization
                   - Asset efficiency
                   - Labor productivity
                   - Inventory management
                   - Supply chain optimization

                3. Quality Metrics:
                   - Defect rates
                   - Customer satisfaction
                   - Service levels
                   - Compliance metrics
                   - Performance standards

                4. Cost Structure:
                   - Fixed vs variable costs
                   - Cost drivers
                   - Efficiency ratios
                   - Cost reduction initiatives
                   - Benchmark comparisons

                Required Output Structure:
                - Efficiency Metrics
                - Resource Optimization
                - Quality Assessment
                - Cost Analysis
                - Improvement Opportunities
                """,
                
            "Growth Trajectory": """
                Analyze growth patterns and future potential. Focus on:

                1. Historical Growth:
                   - Growth rates by segment
                   - Growth drivers
                   - Success factors
                   - Limiting factors
                   - Growth quality

                2. Market Opportunity:
                   - TAM/SAM analysis
                   - Growth vectors
                   - Market dynamics
                   - Competitive space
                   - Entry barriers

                3. Growth Enablers:
                   - Core capabilities
                   - Resource availability
                   - Market access
                   - Innovation pipeline
                   - Strategic assets

                4. Growth Execution:
                   - Implementation roadmap
                   - Resource requirements
                   - Risk factors
                   - Success metrics
                   - Timeline planning

                Required Output Structure:
                - Growth Analysis
                - Market Assessment
                - Capability Review
                - Execution Plan
                - Risk Factors
                """
        }
        
        base_prompt = prompts.get(topic, "Analyze this topic in the financial context")
        return f"""
        Topic: {topic}
        
        Instructions:
        {base_prompt}
        
        Source Summary:
        {summary}
        
        CRITICAL REQUIREMENTS:
        1. Preserve ALL quantitative data
        2. Maintain ALL market signals
        3. Keep ALL strategic insights
        4. Retain ALL risk factors
        5. Save ALL temporal references
        6. Include ALL comparative analyses
        7. Flag ALL anomalies and patterns
        8. Highlight ALL actionable insights
        """

    async def group_and_analyze(self, summaries: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """
        Group and analyze summaries by topic.
        
        Args:
            summaries: List of summaries with their metadata
            
        Returns:
            Dictionary mapping topics to lists of relevant points
        """
        logger.info("Grouping and analyzing summaries by topic")
        
        # Initialize results dictionary
        topic_analyses = {topic: [] for topic in self.topics}
        
        # Process each summary
        for summary_data in summaries:
            if not summary_data.get('summary'):
                continue
                
            try:
                # Analyze the summary
                analysis = await self.analyze_summary(summary_data['summary'])
                
                # Add relevant points to each topic
                for topic, points in analysis.items():
                    if points and points.strip():
                        topic_analyses[topic].append(points)
                        
            except Exception as e:
                logger.error(f"Error analyzing summary: {str(e)}")
                continue
        
        return topic_analyses
