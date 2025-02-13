"""Test script for verifying summarization stages."""

import asyncio
import os
import sys
from pathlib import Path
import pytest

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from dotenv import load_dotenv
from clients.openai_client import OpenAIClient
from services.summarizer_service import SummarizerService, SummaryConfig
from services.topic_analyzer import TopicAnalyzer
from services.chunk_manager import ChunkManager
from services.prompt_manager import PromptManager

# Load environment variables
load_dotenv()

# Get OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Sample financial text for testing
SAMPLE_FINANCIAL_TEXT = """
Q4 2023 Financial Performance Overview

Methodology:
This analysis is based on audited financial statements, market research data, and internal performance metrics. All year-over-year (YoY) comparisons are made using consistent accounting principles and measurement methods.

Revenue Growth:
- Total revenue reached $2.45 billion, up 18% YoY
- Subscription revenue grew 22% to $1.8 billion
- Professional services revenue increased 8% to $650 million

Profitability Metrics:
- Gross margin improved to 72% from 68% in Q4 2022
- Operating margin at 15%, up from 12%
- EBITDA margin expanded to 25%

Key Business Highlights:
- Customer base grew to 15,000 enterprise clients
- Net revenue retention rate at 125%
- Average contract value increased by 15% to $185,000
- International revenue now represents 35% of total revenue

Market Dynamics:
- Observed increased competition in APAC region
- Supply chain costs decreased by 12% QoQ
- Raw material prices stabilized after volatile Q3

Forward-Looking Analysis:
- Projecting 20-22% revenue growth for FY2024
- Planning expansion into emerging markets
- R&D investments to increase by 25%
- Targeting operating margin of 18% by Q4 2024

Risk Assessment:
- Ongoing geopolitical tensions affecting EMEA operations
- Currency fluctuations impact on international revenue
- Potential regulatory changes in data privacy

Recommendations:
1. Accelerate APAC market penetration to counter competition
2. Implement currency hedging strategies for international operations
3. Increase R&D focus on data privacy compliance tools
4. Explore strategic partnerships in emerging markets

Next Steps:
- Review pricing strategy in competitive regions
- Develop comprehensive risk mitigation plan
- Schedule quarterly progress reviews on market expansion
- Initialize data privacy enhancement program
"""

@pytest.mark.asyncio
async def test_summarization_pipeline():
    """Test the entire summarization pipeline with different models."""
    models = ['gpt-4', 'o1-preview']
    
    for model in models:
        try:
            print(f"\n=== Testing Summarization Pipeline with {model} ===")
            # Initialize clients and services
            openai_client = OpenAIClient(api_key)
            chunk_manager = ChunkManager()
            prompt_manager = PromptManager()
            summarizer = SummarizerService(openai_client, chunk_manager, prompt_manager)
            topic_analyzer = TopicAnalyzer(openai_client)
            
            # Create summary config
            config = SummaryConfig(
                model=model,
                context_window=8192,
                max_output_tokens=4000,
                min_output_tokens=1000
            )
        
            print("\n=== Testing Initial Summary Generation ===")
            initial_summary = await summarizer.process_report_text(
                text=SAMPLE_FINANCIAL_TEXT,
                config=config,
                name="test_report.pdf"
            )
            if not initial_summary:
                raise ValueError(f"Failed to generate initial summary with {model}")
                
            print("\nInitial Summary:")
            print(initial_summary)
            print("\nInitial Summary Token Count:", len(initial_summary.split()))
            
            print("\n=== Testing Topic Analysis ===")
            topic_analyses = await topic_analyzer.analyze_summary(initial_summary)
            if not topic_analyses:
                raise ValueError(f"Failed to generate topic analyses with {model}")
                
            print("\nTopic Analyses:")
            for topic, analysis in topic_analyses.items():
                print(f"\n{topic}:")
                print(analysis)
                print(f"Token Count: {len(analysis.split())}")
            
            print("\n=== Testing Final Summary Generation ===")
            combined_text = "\n\n===\n\n".join(topic_analyses.values())
            final_summary = await summarizer.generate_final_analysis(
                combined_summary=combined_text,
                model=model
            )
            if not final_summary:
                raise ValueError(f"Failed to generate final summary with {model}")
                
            print("\nFinal Summary:")
            print(final_summary)
            print("\nFinal Summary Token Count:", len(final_summary.split()))
            print("\n=== Successfully completed pipeline with", model, "===\n")
            
        except Exception as e:
            print(f"Error testing {model}: {e}")

if __name__ == "__main__":
    asyncio.run(test_summarization_pipeline())
