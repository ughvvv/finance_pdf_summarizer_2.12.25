import logging
import smtplib
import backoff
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional, Any
import re
from config import Config

logger = logging.getLogger(__name__)

class EmailFormatter:
    """Handles HTML email formatting with improved financial report styling"""

    @staticmethod
    def create_html_email(analysis: str) -> str:
        """Convert the analysis into a well-formatted HTML email"""
        if not analysis or analysis.strip() == "":
            logger.error("Received empty analysis content")
            return "<p>Error: No analysis content available</p>"

        # Log the incoming analysis content
        logger.debug(f"Formatting analysis content:\n{analysis[:1000]}...")

        css = """
        <style>
            :root {
                --primary-bg: #ffffff;
                --section-bg: #f8f9fa;
                --text-primary: #2d3748;
                --text-secondary: #4a5568;
                --text-header: #1a365d;
                --accent-primary: #3182ce;
                --accent-secondary: #4299e1;
                --metric-positive: #38a169;
                --metric-negative: #e53e3e;
                --border-light: #e2e8f0;
                --card-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --primary-bg: #1a202c;
                    --section-bg: #2d3748;
                    --text-primary: #f7fafc;
                    --text-secondary: #e2e8f0;
                    --text-header: #90cdf4;
                    --accent-primary: #4299e1;
                    --accent-secondary: #63b3ed;
                    --metric-positive: #48bb78;
                    --metric-negative: #fc8181;
                    --border-light: #4a5568;
                }
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.7;
                color: var(--text-primary);
                max-width: 1200px;
                margin: 0 auto;
                padding: 40px 20px;
                background-color: var(--primary-bg);
                font-size: 16px;
            }

            /* Executive Summary Card */
            .executive-summary {
                background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
                color: white;
                padding: 30px;
                border-radius: 16px;
                margin: 0 0 40px 0;
                box-shadow: var(--card-shadow);
            }

            .executive-summary h2 {
                color: white;
                border: none;
                margin-top: 0;
                font-size: 24px;
                padding: 0;
            }

            /* Section Cards */
            .section-card {
                background: var(--section-bg);
                border-radius: 12px;
                padding: 30px;
                margin: 30px 0;
                box-shadow: var(--card-shadow);
                border: 1px solid var(--border-light);
            }

            /* Headers */
            h1 {
                color: var(--text-header);
                font-size: 32px;
                font-weight: 700;
                margin: 0 0 40px 0;
                padding-bottom: 16px;
                border-bottom: 3px solid var(--accent-primary);
            }

            h2 {
                color: var(--text-header);
                font-size: 24px;
                font-weight: 600;
                margin: 30px 0 20px 0;
                padding-left: 16px;
                border-left: 4px solid var(--accent-primary);
            }

            h3 {
                color: var(--text-header);
                font-size: 20px;
                font-weight: 600;
                margin: 25px 0 15px 0;
            }

            /* Metrics and Data Points */
            .metric-card {
                background: var(--primary-bg);
                border-radius: 8px;
                padding: 20px;
                margin: 15px 0;
                border: 1px solid var(--border-light);
            }

            .metric-positive {
                color: var(--metric-positive);
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
                background: rgba(56, 161, 105, 0.1);
                display: inline-block;
            }

            .metric-negative {
                color: var(--metric-negative);
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 4px;
                background: rgba(229, 62, 62, 0.1);
                display: inline-block;
            }

            .highlight {
                background: rgba(49, 130, 206, 0.1);
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 500;
                display: inline-block;
            }

            /* Lists */
            ul {
                margin: 20px 0;
                padding-left: 0;
                list-style: none;
            }

            li {
                margin: 12px 0;
                padding-left: 24px;
                position: relative;
                line-height: 1.6;
            }

            li:before {
                content: "•";
                color: var(--accent-primary);
                font-weight: bold;
                position: absolute;
                left: 0;
            }

            /* Tables */
            .table-wrapper {
                margin: 25px 0;
                overflow-x: auto;
                border-radius: 8px;
                box-shadow: var(--card-shadow);
            }

            table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: var(--primary-bg);
            }

            th {
                background: var(--accent-primary);
                color: white;
                font-weight: 600;
                text-align: left;
                padding: 16px;
                border-bottom: 2px solid var(--border-light);
            }

            td {
                padding: 14px 16px;
                border-bottom: 1px solid var(--border-light);
                color: var(--text-secondary);
            }

            tr:last-child td {
                border-bottom: none;
            }

            /* Key Points and Insights */
            .insight-card {
                background: var(--primary-bg);
                border-left: 4px solid var(--accent-primary);
                padding: 20px;
                margin: 20px 0;
                border-radius: 0 8px 8px 0;
            }

            .key-point {
                background: rgba(49, 130, 206, 0.1);
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
            }

            /* Footer */
            .footer {
                margin-top: 60px;
                padding-top: 30px;
                border-top: 2px solid var(--border-light);
                color: var(--text-secondary);
                font-size: 14px;
            }

            /* Responsive Design */
            @media (max-width: 768px) {
                body {
                    padding: 20px;
                    font-size: 15px;
                }

                .section-card {
                    padding: 20px;
                    margin: 20px 0;
                }

                h1 {
                    font-size: 28px;
                    margin-bottom: 30px;
                }

                h2 {
                    font-size: 22px;
                }

                h3 {
                    font-size: 18px;
                }

                .executive-summary {
                    padding: 25px;
                    margin-bottom: 30px;
                }
            }
        </style>
        """

        def process_bold_text(text: str) -> str:
            """Convert markdown bold syntax to HTML strong tags"""
            return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

        def convert_md_table_to_html(md_table: str) -> str:
            """Convert markdown tables to HTML with improved formatting"""
            md_table = process_bold_text(md_table)
            rows = md_table.strip().split('\n')
            html_rows = []
            for i, row in enumerate(rows):
                cells = row.strip('|').split('|')
                cell_type = 'th' if i <= 1 else 'td'
                html_cells = []
                for cell in cells:
                    cell_content = cell.strip()
                    if '%' in cell_content:
                        if '+' in cell_content:
                            cell_content = f'<span class="metric-positive">{cell_content}</span>'
                        elif '-' in cell_content:
                            cell_content = f'<span class="metric-negative">{cell_content}</span>'
                    elif '$' in cell_content:
                        cell_content = f'<span class="highlight">{cell_content}</span>'
                    html_cells.append(f'<{cell_type}>{cell_content}</{cell_type}>')
                html_rows.append(f"<tr>{''.join(html_cells)}</tr>")
            return f'<div class="table-wrapper"><table>{"".join(html_rows)}</table></div>'

        try:
            # Process the analysis text
            # Clean up separators and extra whitespace
            analysis = re.sub(r'^\s*[-─]{3,}\s*$', '', analysis, flags=re.MULTILINE)
            analysis = re.sub(r'\n{3,}', '\n\n', analysis)
            
            # Add spacing between sections
            analysis = re.sub(r'(#+ [^\n]+)\n', r'\1\n\n', analysis)
            
            html_content = process_bold_text(analysis)
            
            # Extract and format executive summary if it exists
            summary_match = re.search(r'# Summary(.*?)(?=\n#|\Z)', analysis, re.DOTALL)
            if summary_match:
                summary_content = summary_match.group(1).strip()
                summary_html = f"""
                <div class="executive-summary">
                    <h2>Executive Summary</h2>
                    {process_bold_text(summary_content)}
                </div>
                """
                html_content = html_content.replace(summary_match.group(0), summary_html)
            
            # Convert bullet points and lists
            html_content = re.sub(r'^\s*[-•]\s*(.*?)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
            html_content = re.sub(r'(<li>.*?</li>\s*)+', r'<ul>\g<0></ul>', html_content)
            
            # Convert markdown headers and wrap in section cards
            html_content = re.sub(r'# (.*?)\n', r'<h1>\1</h1>', html_content)
            html_content = re.sub(r'## (.*?)\n', r'</div><div class="section-card"><h2>\1</h2>', html_content)
            html_content = re.sub(r'### (.*?)\n', r'<h3>\1</h3>', html_content)
            
            # Format metrics and data points
            metrics_pattern = r'(\d+\.?\d*%|\$\d+(?:\.\d+)?(?:k|M|B|T)?|\d+\.?\d*x)'
            html_content = re.sub(
                metrics_pattern,
                lambda m: f'<span class="highlight">{m.group(1)}</span>',
                html_content
            )
            
            # Format positive/negative metrics
            html_content = re.sub(r'(\+\d+\.?\d*%)', r'<span class="metric-positive">\1</span>', html_content)
            html_content = re.sub(r'(-\d+\.?\d*%)', r'<span class="metric-negative">\1</span>', html_content)
            
            # Convert tables
            table_pattern = r'\|.*?\|[\s\S]*?(?=\n\n|\Z)'
            tables = re.finditer(table_pattern, html_content)
            for table in tables:
                html_table = convert_md_table_to_html(table.group())
                html_content = html_content.replace(table.group(), html_table)
            
            # Wrap content in section cards
            html_content = '<div class="section-card">' + html_content + '</div>'
            
            # Add footer
            footer = f"""
            <div class="footer">
                <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p PST')}</p>
                <p>Data sources include Bloomberg, Reuters, IMF, World Bank, and company financial reports.</p>
                <p>Past performance is not indicative of future results. All investments involve risks.</p>
            </div>
            """
            
            return f"""
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <meta name="color-scheme" content="light dark">
                    {css}
                </head>
                <body>
                    <h1>Daily Financial Analysis Report</h1>
                    {html_content}
                    {footer}
                </body>
            </html>
            """
        except Exception as e:
            logger.error(f"Error formatting HTML email: {e}", exc_info=True)
            return f"""
            <p>Error formatting analysis content: {str(e)}</p>
            <pre>{analysis}</pre>
            """

class EmailSender:
    """Handles email sending with retry logic"""

    def __init__(self, config: Config):
        self.config = config
        self.formatter = EmailFormatter()

    @backoff.on_exception(backoff.expo, (smtplib.SMTPException, ConnectionError), max_tries=5)
    async def send_analysis_email(self, analysis: str, subject: Optional[str] = None):
        """Send the analysis email with retries."""
        try:
            logger.info("Preparing to send analysis email")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject or f"Daily Financial Analysis Report - {datetime.now().strftime('%B %d, %Y')}"
            msg['From'] = self.config.sender_email
            msg['To'] = self.config.recipient_email
            html_content = self.formatter.create_html_email(analysis)
            msg.attach(MIMEText(html_content, 'html'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.config.sender_email, self.config.email_password)
                server.send_message(msg)
            logger.info("Analysis email sent successfully")
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            raise
