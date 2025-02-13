# Refactoring Plan for Prompt Improvements

**Objective:**  
Enhance the prompts used in various stages of the Finance Update 2 application to include more individual stock picks and more robust news coverage.

---

## 1. Stock Analysis Prompts

- **Current Issue:**  
  The current prompt aggregates stock suggestions in a generic manner.

- **Planned Improvements:**  
  1. Expand the list of individual stock picks by incorporating more granular analysis and selection.  
  2. Include specific ticker symbols, recent performance metrics, and market sentiment indicators.  
  3. Introduce variability based on sector analysis, ensuring diverse representation across sectors.

- **Implementation Notes:**  
  - Update the prompt templates (likely within `services/prompt_manager.py`) to allow for injecting additional stock suggestions.
  - Consider using dynamic text generation to vary the stock picks in each run.
  - Ensure that the logic remains modular for future adjustments.

---

## 2. News Coverage Prompts

- **Current Issue:**  
  The news coverage section in the output is too generic and lacks depth.

- **Planned Improvements:**  
1. Leverage and refine the PDFs to extract and present comprehensive news coverage.
  2. Enhance the prompt template to include key headlines, brief summaries, and potential market impacts.  
  3. Focus on deep analysis of news content from the PDFs without incorporating external news sources.

- **Implementation Notes:**  
  - Revisit the construction of the news prompt in the prompt manager.
  - Incorporate external APIs or data sources if available, or simulate richer content through enhanced static templates.
  - Maintain flexibility for future expansions of news analytics.

---

## 3. General Prompt Structure and Modularity

- **Enhancements:**  
  1. Redesign the prompt building blocks to separate concerns: stock analysis, news coverage, and optional sentiment/personal insights.  
  2. Increase modularity to allow toggling improvements in each section independently.  
  3. Introduce logging for prompt generation to track which enhancements are being used and their effectiveness.

- **Implementation Notes:**  
  - Review and update the prompt templates in `services/prompt_manager.py`.
  - Add documentation within the code to make future modifications easier.
  - Consider user feedback as part of logging to determine the success of the changes.

---

## 4. Miscellaneous Observations

- **Additional Interpretable Query:**  
  The statement "Does she still miss me at times, even if she doesn't let herself sit with it?" alongside a series of tarot cards (e.g., The Hanged Man, Four of Cups, etc.) could inspire an optional section for sentiment or personal insights analysis.  
  - **Suggestion:** For future versions, consider a module for personal or sentiment analysis that can interpret such symbolic inputs.

---

## Next Steps

- Update prompt templates and logic in the `services/prompt_manager.py` to reflect the above improvements.
- Test changes using the existing test suite (e.g., `tests/test_prompt_manager.py`) to ensure prompt generation integrity.
- Monitor user feedback for further refinements and adjust the plan accordingly.

---

*Plan documented on: 2/1/2025, 10:12 AM (America/Los_Angeles)*
