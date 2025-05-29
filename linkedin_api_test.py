# improved_app.py
import streamlit as st
import json
import os
import fitz
from datetime import datetime
from agno.utils.pprint import pprint_run_response
from typing import Iterator, Dict, Any
from agno.agent import Agent, RunResponse
import pandas as pd
import asyncio
# Enhanced main.py with batch resume customization

import os
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import time

from dotenv import load_dotenv
from agno.agent import Agent, RunResponse
from agno.models.ollama import Ollama
from agno.models.aws import AwsBedrock
from agno.utils.pprint import pprint_run_response

from linkedin_api import Linkedin
from langchain_community.document_loaders import CSVLoader
from langchain_core.documents import Document
from resume_customizer import ResumeCustomizer

load_dotenv()


def init_linkedin_api():
    """Initialize LinkedIn API client"""
    user_name = os.getenv('LINKEDIN_NAME')
    user_pass = os.getenv('LINKEDIN_PASSWORD')

    if not user_name or not user_pass:
        print("LinkedIn credentials not found in .env file")
        return None

    try:
        api = Linkedin(user_name, user_pass)
        return api
    except Exception as e:
        print(f"Error initializing LinkedIn API: {e}")
        return None


def search_jobs() -> str:
    """
    Search for jobs on LinkedIn based on criteria
    Args:
        keywords (Optional[str]): Keywords to search for in job titles or descriptions.
        companies (Optional[List[str]]): List of company names to filter jobs by.
        location_name (Optional[str]): Name of the location to filter jobs by.
        listed_at (int, optional): Time in seconds since epoch when the job was listed. Defaults to 86400.
        limit (int, optional):Maximum number of jobs to fetch. Defaults to 10.

    Returns:
        list: List of job postings that match the criteria.
    """
    linkedin_api = init_linkedin_api()
    # Simulate delay for testing
    if not linkedin_api:
        # Return mock data for testing
        return "Error: LinkedIn API not initialized. Please check your credentials."

    try:
        print("Using LinkedIn API to search for jobs...")

        jobs = linkedin_api.search_jobs(
            keywords="Software Engineer at Amazon",
            location_name="India",
            limit=10,
            easy_apply=True)  #need to be replaced by limit

        job_results = []
        for job in jobs:
            job_id = job["entityUrn"].split(":")[-1]
            print(f"Processing job ID: {job_id}")

            try:
                # Get detailed job information
                job_data = linkedin_api.get_job(job_id=job_id)
                job_skills = linkedin_api.get_job_skills(job_id=job_id)

                # Extract job details
                job_title = job_data.get("title", "Unknown Title")
                company_details = job_data.get("companyDetails", {}).get(
                    "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany",
                    {})
                company_name = company_details.get("companyResolutionResult",
                                                   {}).get(
                                                       "name",
                                                       "Unknown Company")
                job_description = job_data.get("description", {}).get(
                    "text", "No description available")
                job_location = job_data.get("formattedLocation",
                                            "Unknown Location")
                easy_apply = job_data.get("applyMethod",
                                          {}).get("easyApplyUrl") is not None

                company_apply_url = None

                print(job_data)
                print("-" * 80)

                if not easy_apply:
                    print("skip")

                    company_apply_url = job_data.get("applyMethod", {}).get(
                        "com.linkedin.voyager.jobs.OffsiteApply",
                        {}).get("companyApplyUrl")
                    continue

                job_result = {
                    "job_id": job_id,
                    "title": job_title,
                    "company": company_name,
                    "location": job_location,
                    "description":
                    job_description,  # Full description for resume customization
                    "easy_apply": easy_apply,
                    "url": f"https://www.linkedin.com/jobs/view/{job_id}",
                    "posted_date": datetime.now().isoformat(),
                    "company_apply_url": company_apply_url
                }

                job_results.append(job_result)

                # Add delay to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
                continue

        print("returning results")

        return json.dumps(job_results, indent=2)

    except Exception as e:
        return f"Error searching jobs: {e}"


def _create_simple_docx(text: str, output_path: str) -> bool:
    """Create professional DOCX resume with proper formatting."""
    try:
        from docx import Document
        from docx.shared import Inches, Pt
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        import re

        # Create a new document
        doc = Document()

        # Set margins for professional resume
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)

        # Split text into lines for processing
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Handle name (first line, main heading)
            if line.startswith('# '):
                name = line[2:].strip()
                name_paragraph = doc.add_heading(name, level=1)
                name_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

            # Handle section headings
            elif line.startswith('## '):
                section_title = line[3:].strip()
                doc.add_heading(section_title, level=2)

            # Handle contact information (Email, LinkedIn, Mobile)
            elif any(
                    line.startswith(contact)
                    for contact in ['Email:', 'Linkedin:', 'Mobile:']):
                contact_paragraph = doc.add_paragraph()
                contact_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

                # Clean up the contact info
                if line.startswith('Linkedin:'):
                    line = line.replace('//', 'linkedin.com/in/')

                run = contact_paragraph.add_run(line)
                run.font.name = 'Calibri'
                run.font.size = Pt(11)

            # Handle education entries
            elif line.startswith('• **') and ('Institute' in line
                                              or 'University' in line
                                              or 'College' in line):
                # Institution name
                institution = re.sub(r'• \*\*([^*]+)\*\*', r'\1', line)
                inst_paragraph = doc.add_paragraph()
                inst_run = inst_paragraph.add_run(institution)
                inst_run.bold = True
                inst_run.font.size = Pt(12)

                # Process following lines for education details
                i += 1
                while i < len(lines) and lines[i].strip(
                ) and not lines[i].startswith(('•', '#')):
                    detail_line = lines[i].strip()
                    if detail_line == 'India':  # Skip country line or make it part of institution
                        pass
                    elif 'Bachelor' in detail_line or 'Master' in detail_line or 'GPA' in detail_line:
                        degree_paragraph = doc.add_paragraph(detail_line)
                        degree_paragraph.paragraph_format.left_indent = Inches(
                            0.25)
                    elif re.match(r'\d{4}\s*-\s*\d{4}', detail_line):
                        date_paragraph = doc.add_paragraph(detail_line)
                        date_paragraph.paragraph_format.left_indent = Inches(
                            0.25)
                    i += 1
                i -= 1  # Adjust for the outer loop increment

            # Handle skills section
            elif line.startswith('• **') and ':' in line:
                # Skill category
                skill_category = re.sub(r'• \*\*([^*]+)\*\*:', r'\1:', line)
                skill_paragraph = doc.add_paragraph()

                # Split category and content
                if ':' in skill_category:
                    category, content = skill_category.split(':', 1)
                    cat_run = skill_paragraph.add_run(f"{category}: ")
                    cat_run.bold = True
                    cat_run.font.size = Pt(11)

                    content_run = skill_paragraph.add_run(content.strip())
                    content_run.font.size = Pt(11)

            # Handle experience entries
            elif line.startswith('• **ORGANIZATION:') or line.startswith(
                    '• **Organization:') or line.startswith(
                        '• **ORGANISATION:'):
                # Company name
                company = re.sub(r'• \*\*ORGANI[SZ]ATION:\s*([^*]+)\*\*',
                                 r'\1', line)
                company_paragraph = doc.add_paragraph()
                company_run = company_paragraph.add_run(company)
                company_run.bold = True
                company_run.font.size = Pt(12)

                # Process role and dates
                i += 1
                while i < len(lines) and lines[i].strip(
                ) and not lines[i].startswith('•'):
                    detail_line = lines[i].strip()

                    if detail_line.startswith(
                            '**ROLE:') or detail_line.startswith('**Role:'):
                        role = re.sub(r'\*\*ROLE?:\s*([^*]+)\*\*', r'\1',
                                      detail_line)
                        role_paragraph = doc.add_paragraph(role)
                        role_paragraph.paragraph_format.left_indent = Inches(
                            0.25)
                        role_run = role_paragraph.runs[0]
                        role_run.italic = True
                        role_run.font.size = Pt(11)

                    elif re.search(
                            r'(January|February|March|April|May|June|July|August|September|October|November|December|\d{4})',
                            detail_line):
                        date_paragraph = doc.add_paragraph(detail_line)
                        date_paragraph.paragraph_format.left_indent = Inches(
                            0.25)

                    elif detail_line.startswith('◦'):
                        # Experience bullet points
                        bullet_text = detail_line[1:].strip()
                        bullet_paragraph = doc.add_paragraph(
                            bullet_text, style='List Bullet')
                        bullet_paragraph.paragraph_format.left_indent = Inches(
                            0.5)

                    elif detail_line == 'Freelancing':
                        freelance_paragraph = doc.add_paragraph(detail_line)
                        freelance_paragraph.paragraph_format.left_indent = Inches(
                            0.25)

                    i += 1
                i -= 1

            # Handle project entries
            elif line.startswith('◦ **') and not line.startswith('◦ **Task:'):
                # Project title
                project_title = re.sub(r'◦ \*\*([^*]+)\*\*', r'\1', line)
                project_paragraph = doc.add_paragraph()
                project_run = project_paragraph.add_run(project_title)
                project_run.bold = True
                project_run.font.size = Pt(11)

                # Process project details
                i += 1
                while i < len(lines) and lines[i].strip(
                ) and not lines[i].startswith('◦ **'):
                    detail_line = lines[i].strip()

                    if detail_line.startswith('∗**Task:**'):
                        task_text = detail_line[10:].strip(
                        )  # Remove ∗**Task:**
                        task_paragraph = doc.add_paragraph(
                            f"Task: {task_text}")
                        task_paragraph.paragraph_format.left_indent = Inches(
                            0.25)

                    elif detail_line.startswith('∗**Technologies:**'):
                        tech_text = detail_line[17:].strip(
                        )  # Remove ∗**Technologies:**
                        tech_paragraph = doc.add_paragraph(
                            f"Technologies: {tech_text}")
                        tech_paragraph.paragraph_format.left_indent = Inches(
                            0.25)
                        tech_run = tech_paragraph.runs[0]
                        # Make "Technologies:" bold
                        tech_paragraph.clear()
                        bold_run = tech_paragraph.add_run("Technologies: ")
                        bold_run.bold = True
                        normal_run = tech_paragraph.add_run(tech_text)

                    i += 1
                i -= 1

            # Handle certifications and regular bullets
            elif line.startswith('• '):
                bullet_text = line[2:].strip()
                # Clean up markdown formatting
                bullet_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', bullet_text)
                bullet_text = bullet_text.replace('//', 'https://')

                bullet_paragraph = doc.add_paragraph(bullet_text,
                                                     style='List Bullet')

            # Handle links in articles
            elif '//' in line:
                link_text = line.replace('//', 'https://')
                link_paragraph = doc.add_paragraph(link_text)
                link_paragraph.paragraph_format.left_indent = Inches(0.25)

            # Handle any other regular text
            else:
                if line and not line.startswith(('◦', '∗')):
                    clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
                    doc.add_paragraph(clean_text)

            i += 1

        # Save the document
        doc.save(output_path)

        print(f"Successfully created professional resume DOCX: {output_path}")
        return True

    except ImportError as e:
        print(f"python-docx library not installed: {e}")
        return False
    except Exception as e:
        print(f"Error creating DOCX: {e}")
        return False


import re
import subprocess
import os
import tempfile
from typing import Dict, List, Tuple

import re
import subprocess
import os
import tempfile
import shutil
from pathlib import Path


def create_agent_safe_latex_resume(text: str, output_path: str) -> bool:
    """Create LaTeX resume that works reliably in agent environments."""

    def find_pdflatex():
        """Find pdflatex executable in various locations."""
        possible_paths = [
            'pdflatex',  # In PATH
            '/usr/bin/pdflatex',  # Linux
            '/usr/local/bin/pdflatex',  # Linux/macOS
            '/Library/TeX/texbin/pdflatex',  # macOS MacTeX
            '/usr/local/texlive/2023/bin/x86_64-linux/pdflatex',  # TeXLive
            '/usr/local/texlive/2024/bin/x86_64-linux/pdflatex',  # TeXLive
        ]

        for path in possible_paths:
            if shutil.which(path):
                return path

        return None

    def clean_text_robust(text):
        """Ultra-robust text cleaning for LaTeX."""
        if not text:
            return ""

        # Handle special characters very carefully
        text = str(text)  # Ensure it's a string

        # Order matters - backslash first!
        replacements = [
            ('\\', '\\textbackslash{}'),
            ('{', '\\{'),
            ('}', '\\}'),
            ('$', '\\$'),
            ('&', '\\&'),
            ('%', '\\%'),
            ('#', '\\#'),
            ('^', '\\textasciicircum{}'),
            ('_', '\\_'),
            ('~', '\\textasciitilde{}'),
        ]

        for old, new in replacements:
            text = text.replace(old, new)

        # Convert markdown formatting
        text = re.sub(r'\*\*([^*]+?)\*\*', r'\\textbf{\1}', text)
        text = re.sub(r'\*([^*]+?)\*', r'\\textit{\1}', text)

        # Fix URLs
        text = re.sub(r'//([^\s]+)', r'https://\1', text)

        # Remove any remaining problematic characters
        text = re.sub(r'[^\w\s\.,;:()\[\]/@\-+\\{}]', '', text)

        return text.strip()

    # Minimal LaTeX template to avoid package conflicts
    latex_template = r"""
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=0.75in]{geometry}

% Basic formatting only
\renewcommand{\familydefault}{\sfdefault}
\pagestyle{empty}

% Simple section formatting
\makeatletter
\renewcommand{\section}[1]{%
  \vspace{12pt}%
  {\large\bfseries #1}%
  \vspace{6pt}%
  \hrule%
  \vspace{6pt}%
}
\makeatother

\begin{document}

%CONTENT%

\end{document}
"""

    try:
        # Check if pdflatex is available
        pdflatex_path = find_pdflatex()
        if not pdflatex_path:
            print("Error: pdflatex not found in system PATH")
            print("Available paths checked:")
            print("- Standard PATH locations")
            print("- /usr/bin/pdflatex")
            print("- /usr/local/bin/pdflatex")
            print("- /Library/TeX/texbin/pdflatex")
            return False

        print(f"Using pdflatex at: {pdflatex_path}")

        # Parse content very simply
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        latex_content = ""

        for line in lines:
            # Name (main title)
            if line.startswith('# '):
                name = clean_text_robust(line[2:])
                latex_content += f"\\begin{{center}}\\Huge\\textbf{{{name}}}\\\\[0.5cm]\\end{{center}}\n\n"

            # Section headers
            elif line.startswith('## '):
                section = clean_text_robust(line[3:])
                latex_content += f"\\section{{{section}}}\n\n"

            # Contact info (center these)
            elif any(
                    line.startswith(x)
                    for x in ['Email:', 'Linkedin:', 'Mobile:']):
                contact = clean_text_robust(line)
                latex_content += f"\\begin{{center}}{contact}\\end{{center}}\n"

            # Bullet points - convert to simple paragraphs to avoid itemize issues
            elif line.startswith(('• ', '- ', '* ')):
                bullet_text = clean_text_robust(line[2:])
                if bullet_text:
                    latex_content += f"\\noindent $\\bullet$ {bullet_text}\\\\[0.2cm]\n"

            # Sub-bullets
            elif line.startswith('◦ '):
                sub_bullet = clean_text_robust(line[2:])
                if sub_bullet:
                    latex_content += f"\\hspace{{0.5cm}}$\\circ$ {sub_bullet}\\\\[0.1cm]\n"

            # Regular paragraphs
            else:
                clean_line = clean_text_robust(line)
                if clean_line:
                    latex_content += f"{clean_line}\\\\[0.2cm]\n"

        # Create full document
        full_latex = latex_template.replace('%CONTENT%', latex_content)

        # Use absolute paths and proper error handling
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Write LaTeX file
            tex_file = temp_dir / 'resume.tex'
            tex_file.write_text(full_latex, encoding='utf-8')

            # Save debug copy
            debug_path = Path(output_path).with_suffix('.tex')
            debug_path.write_text(full_latex, encoding='utf-8')
            print(f"Debug LaTeX saved to: {debug_path}")

            # Set environment variables for LaTeX
            env = os.environ.copy()
            env['TEXMFOUTPUT'] = str(temp_dir)

            # Compile with full path and environment
            cmd = [
                str(pdflatex_path), '-output-directory',
                str(temp_dir), '-interaction=nonstopmode', '-halt-on-error',
                str(tex_file)
            ]

            print(f"Running command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=str(temp_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            if result.returncode != 0:
                print(
                    f"LaTeX compilation failed with return code: {result.returncode}"
                )
                print("STDOUT:", result.stdout[-1000:])  # Last 1000 chars
                print("STDERR:", result.stderr[-1000:])

                # Check log file
                log_file = temp_dir / 'resume.log'
                if log_file.exists():
                    log_content = log_file.read_text()
                    print("\nRelevant log lines:")
                    for line in log_content.split('\n'):
                        if any(keyword in line.lower() for keyword in
                               ['error', '!', 'undefined', 'missing']):
                            print(f"  {line}")

                return False

            # Copy PDF to final location
            pdf_file = temp_dir / 'resume.pdf'
            if pdf_file.exists():
                # Use shutil.copy2 for better compatibility
                shutil.copy2(str(pdf_file), output_path)
                print(f"Successfully created PDF: {output_path}")
                return True
            else:
                print("PDF file was not created")
                return False

    except subprocess.TimeoutExpired:
        print("LaTeX compilation timed out (>30 seconds)")
        return False
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


# Test function to verify environment
def test_latex_environment():
    """Test if LaTeX is properly set up."""
    print("Testing LaTeX environment...")

    # Check pdflatex
    if shutil.which('pdflatex'):
        print("✓ pdflatex found in PATH")

        # Test basic compilation
        test_latex = r"""
\documentclass{article}
\begin{document}
Hello World!
\end{document}
"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                tex_file = Path(temp_dir) / 'test.tex'
                tex_file.write_text(test_latex)

                result = subprocess.run([
                    'pdflatex', '-output-directory', temp_dir,
                    '-interaction=nonstopmode',
                    str(tex_file)
                ],
                                        capture_output=True,
                                        timeout=10)

                if result.returncode == 0:
                    print("✓ LaTeX compilation test successful")
                    return True
                else:
                    print("✗ LaTeX compilation test failed")
                    print("Error:", result.stderr[:200])
        except Exception as e:
            print(f"✗ LaTeX test error: {e}")
    else:
        print("✗ pdflatex not found in PATH")

    return False


# Usage for agents:
def safe_create_resume(text: str, output_path: str) -> bool:
    """Entry point that tests environment first."""
    if not test_latex_environment():
        print("LaTeX environment not properly configured")
        return False

    return create_agent_safe_latex_resume(text, output_path)


# Example usage:
# resume_text = """Your resume text here"""
# create_latex_resume(resume_text, "resume.pdf")

if __name__ == "__main__":
    result = search_jobs()
    print(result)
