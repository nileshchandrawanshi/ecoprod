from bs4 import BeautifulSoup
import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone
import urllib3
from dateutil import parser
import pytz

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JIRA_URL = os.getenv("JIRA_URL")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

def convert_to_wiki_markup(summary):
    # Add Jira wiki formatting for the description
    formatted_summary = f"h3. Summary\n{summary}\n\n"
    formatted_summary += "*Note*: This issue was auto-created from the RSS feed."
    return formatted_summary

def create_jira_ticket(title, summary, component):
    issue_data = {
        "fields": {
            "project": {
                "key": JIRA_PROJECT_KEY
            },
            "summary": title,
            "description": summary,
            "issuetype": {
                "name": "Change Log"
            },
            "components": [
                {"name": component}
            ]
        }
    }

    response = requests.post(
        f"{JIRA_URL}/rest/api/2/issue",
        json=issue_data,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Content-Type": "application/json"},
        verify=False  # Disable SSL verification
    )

    if response.status_code == 201:
        issue_key = response.json()["key"]
        print(f"Jira ticket created successfully: {issue_key}")
        return issue_key
    else:
        print(f"Failed to create Jira ticket: {response.status_code} - {response.text}")
        return None

def add_remote_link(issue_key, link_title, link_url):
    # Function to add a remote link to the issue
    link_data = {
        "object": {
            "url": link_url,
            "title": link_title
        }
    }

    response = requests.post(
        f"{JIRA_URL}/rest/api/2/issue/{issue_key}/remotelink",
        json=link_data,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Content-Type": "application/json"},
        verify=False  # Disable SSL verification
    )

    if response.status_code == 201:
        print(f"Remote link added successfully to {issue_key}.")
    else:
        print(f"Failed to add remote link to {issue_key}: {response.status_code} - {response.text}")

def process_rss_feed():
    # Main logic to process the RSS feed
    rss_url = "https://developer.atlassian.com/platform/forge/changelog/rss/a/d5fbfe34-0fd2-42ea-80a9-931f640a2ed9/"
    response = requests.get(rss_url, verify=False)
    
    if response.status_code != 200:
        print(f"Failed to fetch the feed. Status code: {response.status_code}")
        return "Failed to fetch the RSS feed."

    soup = BeautifulSoup(response.content, "xml")
    data = []
    items = soup.find_all("item")
    for item in items:
        title = item.find("title").text if item.find("title") else "N/A"
        link = item.find("link").text if item.find("link") else "N/A"
        pub_date = item.find("pubDate").text if item.find("pubDate") else "N/A"
        description = item.find("description").text if item.find("description") else "N/A"
        category = item.find("category").text if item.find("category") else "General"

        data.append({
            "Title": title,
            "Link": link,
            "Published Date": pub_date,
            "Summary": description,
            "Category": category
        })

    df = pd.DataFrame(data)
    df['Published Date'] = pd.to_datetime(df['Published Date'], errors='coerce').dt.tz_localize('UTC')
    #df['Published Date'] = pd.to_datetime(df['Published Date'], errors='coerce', utc=True)

    # Calculate the time 24 hours ago
    last_24_hours = datetime.now(timezone.utc) - timedelta(hours=24)
    #last_24_hours = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=24)

    #df_last_24_hours = df[df['Published Date'] >= last_24_hours]
    df_last_24_hours = df[df['Published Date'] >= last_24_hours]
    print("All Published Dates:")
    print(df
    ["Published Date"])

    print("Filtered Data (Last 24 Hours):")
    print(df_last_24_hours)
    if not df_last_24_hours.empty:
        print("Creating Jira tickets for RSS feed data published in the last 24 hours...")
        for _, row in df_last_24_hours.iterrows():
            formatted_summary = convert_to_wiki_markup(row["Summary"])
            issue_key = create_jira_ticket(
                title=row["Title"],
                summary=formatted_summary,
                component=row["Category"]
            )
            if issue_key:
                add_remote_link(
                    issue_key=issue_key,
                    link_title="More Details",
                    link_url=row["Link"]
                )
        return "RSS feed processed, Jira tickets created."
    else:
        print("No RSS feed data published in the last 24 hours.")
        return "No new RSS feed data."

# Lambda handler function
def lambda_handler(event, context):
    print("Lambda function started...")
    try:
        result = process_rss_feed()
        return {
            "statusCode": 200,
            "body": result
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"An error occurred: {str(e)}"
        }
