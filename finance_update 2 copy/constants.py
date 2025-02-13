"""Constants for financial report processing"""

# Model configurations
MODEL_CONFIGS = {
    'o1-preview': {
        'context_window': 128000,
        'max_output_tokens': 32768,
        'uses_completion_tokens': True,
        'supports_temperature': False,
        'optimal_chunk_size': 100000,
        'encoding': 'cl100k_base'
    },
    'o1-mini': {
        'context_window': 128000,
        'max_output_tokens': 65536,
        'uses_completion_tokens': True,
        'supports_temperature': False,
        'optimal_chunk_size': 100000,
        'encoding': 'cl100k_base'
    },
    'gpt-4o': {
        'context_window': 128000,
        'max_output_tokens': 16384,
        'min_output_tokens': 4000,
        'uses_completion_tokens': False,
        'supports_temperature': True,
        'optimal_chunk_size': 100000,
        'encoding': 'gpt-4'
    },
    'gpt-4o-mini': {
        'context_window': 128000,
        'max_output_tokens': 16384,
        'min_output_tokens': 4000,
        'uses_completion_tokens': False,
        'supports_temperature': True,
        'optimal_chunk_size': 100000,
        'encoding': 'gpt-4'
    }
}

# Optimized prompt templates focusing on accurate data extraction
PROMPT_TEMPLATES = {
    'DATA_EXTRACTION': {
        'prefix': '''Extract key information from this financial document. 
CRITICAL: Only include information explicitly stated in the document. Do NOT add any external knowledge or assumptions.

Key Requirements:''',
        'key_areas': [
            'EXACT NUMBERS - Extract all numerical data with full context',
            'DIRECT QUOTES - Use exact quotes for important statements',
            'SPECIFIC DATES - Include all mentioned dates and timeframes',
            'SOURCE ATTRIBUTION - Note who said or reported each point'
        ],
        'format_instructions': '''Format each point as:
[Category] 
• [Data Point/Quote]
  - Source: [Who said/reported it]
  - Context: [Surrounding context]
  - Date: [When mentioned/reported]

IMPORTANT: If specific details (source, date, etc.) aren't provided, mark as "Not specified" rather than making assumptions.'''
    },
    'SYNTHESIS': {
        'prefix': '''Combine these extracted data points into a clear summary.
CRITICAL: Only use information from the provided documents.

Key Requirements:''',
        'key_areas': [
            'MAINTAIN PRECISION - Keep exact numbers and quotes',
            'CLEAR SOURCING - Preserve attribution for each point',
            'TIME CONTEXT - Keep all date references',
            'EVIDENCE BASED - Every point must come from the documents'
        ],
        'format_instructions': '''Format the summary with:
1. Key Points (with source and date)
2. Market Data (exact numbers from documents)
3. Important Quotes (with attribution)
4. Upcoming Events (mentioned dates)

IMPORTANT: Do not add analysis or context beyond what's in the documents.'''
    },
    'FINAL_REPORT': {
        'prefix': '''Create a comprehensive report using ONLY the analyzed documents.
CRITICAL: Every point must come from the source materials.

Report Structure:''',
        'key_sections': [
            '1. KEY DEVELOPMENTS (with exact quotes and numbers)',
            '2. MARKET DATA TABLE (all numerical data from documents)',
            '3. IMPORTANT STATEMENTS (direct quotes with attribution)',
            '4. UPCOMING EVENTS (specific dates mentioned)',
            '5. RISKS & OPPORTUNITIES (explicitly stated in documents)'
        ],
        'format_instructions': '''Formatting Requirements:

1. Mobile-Friendly Layout:
   • Short, clear paragraphs
   • Bulleted lists for key points
   • Tables formatted for mobile viewing
   • Clear section breaks

2. Data Presentation:
   • All numbers in clear, readable format
   • Sources clearly attributed
   • Dates prominently displayed
   • Important quotes highlighted

3. Critical Rules:
   • Only use information from the documents
   • Mark missing information as "Not specified"
   • No external analysis or assumptions
   • Preserve exact numbers and quotes

4. Section Format:
   [SECTION TITLE]
   • Key Point
     - Source: [Attribution]
     - Date: [When reported]
     - Context: [From document]'''
    }
}

# Basic extraction patterns
EXTRACTION_PATTERNS = {
    'NUMERICAL': r'(\d+\.?\d*)\s*(%|bps|USD|EUR|GBP|JPY)?',
    'TEMPORAL': r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})',
    'COMPARISON': r'(higher|lower|increased|decreased|rose|fell|gained|lost)\s+by\s+(\d+\.?\d*)\s*(%|bps)?'
}
