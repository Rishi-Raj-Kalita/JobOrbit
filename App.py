import streamlit as st
import json
import os
from datetime import datetime
from main import create_agent,  init_linkedin_api
from agno.utils.pprint import pprint_run_response
from typing import Iterator
from agno.agent import Agent, RunResponse


class AutoApplyUI:
  def __init__(self):
    st.set_page_config(
      page_title="AutoApply Agent",
      page_icon=" ",
      layout="wide"
    )
    self.linkedin_api = init_linkedin_api()
    
  def show_header(self):
    st.title(" AutoApply: Your Automated Job Search Assistant")
    st.markdown("""
    Let AutoApply help you find, customize, and apply to jobs automatically!
    """)

  def show_sidebar(self):
    st.sidebar.title("Settings")
    provider = st.sidebar.selectbox(
      "Select LLM Provider",
      options=['ollama', 'aws'],
      help="Choose the AI model provider"
    )
    return provider

  def show_job_preferences_upload(self):
    st.header(" Job Preferences")
    uploaded_file = st.file_uploader(
      "Upload your job preferences (CSV)",
      type=['csv'],
      help="Upload a CSV file with your job search preferences"
    )
    
    if uploaded_file:
      # Save the uploaded file
      with open('./data/job_pref.csv', 'wb') as f:
        f.write(uploaded_file.getvalue())
      st.success("Job preferences uploaded successfully!")
      
      # Show preview
      st.subheader("Preview of Job Preferences")
      import pandas as pd
      df = pd.read_csv(uploaded_file)
      st.dataframe(df)

  def show_resume_upload(self):
    st.header(" Resume")
    uploaded_resume = st.file_uploader(
      "Upload your base resume (JSON)",
      type=['json'],
      help="Upload your base resume in JSON format"
    )
    
    if uploaded_resume:
      # Save the uploaded resume
      with open('./data/sample_resume.json', 'wb') as f:
        f.write(uploaded_resume.getvalue())
      st.success("Resume uploaded successfully!")

  def show_job_search_interface(self):
    st.header(" Job Search")
    col1, col2 = st.columns(2)
    
    with col1:
      keywords = st.text_input("Job Title/Keywords", "Data Analyst")
      location = st.text_input("Location", "India")
      
    with col2:
      companies = st.text_input("Target Companies (comma-separated)", "Times Internet")
      experience = st.selectbox(
        "Experience Level",
        options=['F', 'C', 'P', 'Director', 'Executive']
      )
      
    return keywords, location, companies.split(','), experience

  def show_action_buttons(self):
    st.header(" Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
      search = st.button("Search Jobs")
    with col2:
      customize = st.button("Customize Resume")
    with col3:
      apply = st.button("Apply to Jobs")
      
    return search, customize, apply

  def show_stats(self):
    st.header(" Application Statistics")
    if os.path.exists("data/memory.json"):
      with open("data/memory.json", "r") as f:
        stats = json.load(f)
      
      col1, col2, col3 = st.columns(3)
      with col1:
        st.metric("Jobs Found", len(stats.get("jobs_found", [])))
      with col2:
        st.metric("Applications Submitted", len(stats.get("applications", [])))
      with col3:
        st.metric("Referrals Requested", len(stats.get("referrals", [])))

  def run_agent_query(self, query: str, provider: str):
    with st.spinner("Agent is working..."):
      agent = create_agent(provider)
      response_stream: Iterator[RunResponse] = agent.run(query)
      pprint_run_response(response_stream, markdown=True)
      
      # Display results in a nice format
      st.subheader(" Agent Response")

  def run(self):
    self.show_header()
    provider = self.show_sidebar()
    
    # Main content
    self.show_job_preferences_upload()
    self.show_resume_upload()
    
    keywords, location, companies, experience = self.show_job_search_interface()
    search, customize, apply = self.show_action_buttons()
    
    # Handle button actions
    if search:
      query = f"Find {keywords} jobs at {', '.join(companies)} in {location} with {experience} experience level"
      self.run_agent_query(query, provider)
      
    if customize:
      query = f"Customize my resume for the found jobs"
      self.run_agent_query(query, provider)
      
    if apply:
      query = f"Apply to all matching jobs with customized resumes"
      self.run_agent_query(query, provider)
    
    # Show statistics
    self.show_stats()
    
    # Show application history
    st.header(" Application History")
    if os.path.exists("data/memory.json"):
      with st.expander("View History"):
        with open("data/memory.json", "r") as f:
          history = json.load(f)
        st.json(history)

if __name__ == "__main__":
  ui = AutoApplyUI()
  ui.run()