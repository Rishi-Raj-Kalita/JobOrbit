"""
AutoApply Agent using Agno
"""

import os
import json
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from dotenv import load_dotenv
from agno.agent import Agent, RunResponse
from agno.models.ollama import Ollama
from agno.models.aws import AwsBedrock
from agno.utils.pprint import pprint_run_response

from linkedin_api import Linkedin
from langchain_community.document_loaders import CSVLoader
from langchain_core.documents import Document

# Import local modules
# from job_description_scraper import JobDescriptionScraper
# from resume_customizer import ResumeCustomizer, EXAMPLE_BASE_RESUME
# from application_submitter import ApplicationSubmitter
# from referral_requester import ReferralRequester
# from memory_system import MemorySystem

# Load environment variables
load_dotenv()

# Initialize memory system
# memory = MemorySystem("data/memory.json")

# Initialize LinkedIn API
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

# Initialize tools
linkedin_api = init_linkedin_api()

# Set up model
def get_model(provider: str):
    """Get LLM model based on provider"""
    if provider == 'ollama':
        return Ollama(id='llama3.1')
    elif provider == 'aws':
        return AwsBedrock(id="anthropic.claude-3-sonnet-20240229-v1:0",aws_region='us-east-1')
    else:
        raise ValueError("Unsupported provider")

# Tool functions for Agno agent
def read_job_preferences() -> str:
    """Read job preferences from CSV file"""
    try:
        loader = CSVLoader(
            file_path='./data/job_pref.csv',
            csv_args={
                'delimiter': ',',
                'fieldnames': ['Company', 'Role', 'Location', 'Priority', 'Referral', 
                              'Job_Type', 'Keywords', 'Exclude_Keywords', 'Experience', 'Placeholder']
            }
        )
        docs = loader.load()
        return "\n\n".join([doc.page_content for doc in docs])
    except Exception as e:
        return f"Error reading job preferences: {e}"

def search_jobs(keywords: Optional[str]=None, companies: Optional[List[str]]=None, location_name: Optional[str] = None, 
               experience: Optional[List[str]] = None, job_type: Optional[List[str]] = None,
               listed_at: int = 86400, limit: int = 10) -> str:
    """
    Search for jobs on LinkedIn based on criteria
    Args:
        keywords (Optional[str]): Keywords to search for in job titles or descriptions.
        companies (Optional[List[str]]): List of company names to filter jobs by.
        location_name (Optional[str]): Name of the location to filter jobs by.
        experience (Optional[List[Union[Literal['1'], Literal['2'], Literal['3'], Literal['4'], Literal['5'], Literal['6']]]]): A list of experience levels, one or many of "1", "2", "3", "4", "5" and "6" (internship, entry level, associate, mid-senior level, director and executive, respectively)
        listed_at (int, optional): Time in seconds since epoch when the job was listed. Defaults to 86400.
        limit (int, optional):Maximum number of jobs to fetch. Defaults to 10.

    Returns:
        list: List of job postings that match the criteria.
    """
    if not linkedin_api:
        # Return mock data for testing
        print("Using mock")
        return json.dumps([
            {
                "job_id": f"job_{i}",
                "title": f"{keywords} {i+1}",
                "company": companies[0] if companies else "Various Companies",
                "location": location_name,
                "description": f"This is a mock job description for {keywords}.",
                "easy_apply": i % 2 == 0
            } for i in range(3)
        ])
    
    try:
        print("using Linkedin API to search for jobs...")
        print("keywords:", keywords)
        print("companies:", companies)
        print("location_name:", location_name)
        print("experience:", experience)
        print("listed_at:", listed_at)
        print("limit:", limit)
        print("-"*80)
        jobs = linkedin_api.search_jobs(
            keywords=keywords, companies=companies, location_name=location_name, experience=experience, listed_at=listed_at, limit=limit
        )
       
        
        # Process and format job results
        job_results = []
        for job in jobs:
            print(job)
            print("-"*80)
            job_id = job["entityUrn"].split(":")[-1]
            
            try:
                job_data = linkedin_api.get_job(job_id=job_id)
                job_skills = linkedin_api.get_job_skills(job_id=job_id)
                
                job_title = job_data.get("title", "Unknown Title")
                company_details = job_data.get("companyDetails", {}).get(
                    "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany", {})
                company_name = company_details.get("companyResolutionResult", {}).get("name", "Unknown Company")
                job_description = job_data.get("description", {}).get("text", "No description available")
                job_location = job_data.get("formattedLocation", "Unknown Location")
                easy_apply = job_data.get("applyMethod", {}).get("easyApplyUrl") is not None
                
                job_result = {
                    "job_id": job_id,
                    "title": job_title,
                    "company": company_name,
                    "location": job_location,
                    "description": job_description,  # Truncate for readability
                    "skills": job_skills,
                    "easy_apply": easy_apply,
                    "url": f"https://www.linkedin.com/jobs/view/{job_id}"
                }
                
                
                
                job_results.append(job_result)
            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
        
        return json.dumps(job_results, indent=2)
    except Exception as e:
        return f"Error searching jobs: {e}"





# Create Agno agent
def create_agent(provider: str = 'ollama'):
    """Create Agno agent with tools"""
    tools = [
        read_job_preferences,
        search_jobs
    ]
    
    return Agent(
        tools=tools,
        show_tool_calls=True,
        model=get_model(provider),
        markdown=True
    )

# Main function to run the agent
def run_agent(query: str, provider: str = 'ollama'):
    """Run the agent with a query"""
    agent = create_agent(provider)
    response_stream = agent.run(query)
    pprint_run_response(response_stream, markdown=True)

# Example usage
if __name__ == "__main__":
    # Update memory timestamp
    
    # Run agent with example query
    run_agent("Find me data engineer jobs at HCLTech in Bangaluru.")