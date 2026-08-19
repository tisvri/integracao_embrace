import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

url = os.getenv("REDCAP_API_URL")
token = os.getenv("REDCAP_API_KEY")

if not url or not token:
    raise ValueError("REDCAP_API_URL and REDCAP_API_KEY must be set in the environment variables.")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Accept": "application/json",   
}

data = {
    "token": f"{token}",
    "content": "event",
    "format": "json",
    "returnFormat": "json"
}

try:
    redcap_request = requests.post(
        url,
        data = data,
        headers = headers,
        timeout = 30
    )
    print("HTTP Status: ", redcap_request.status_code)
    print(redcap_request.text)
    redcap_request.raise_for_status()  # Raise an error for bad responses
    print(redcap_request.json())
except requests.exceptions.Timeout:
    print("Request timed out. Please check your network connection and try again.")
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
    

unique_event_names = set()
try:
    events = redcap_request.json()
    for event in events:
        event_name = event.get('event_name')
        if event_name:
            unique_event_names.add(event_name)
    print("Unique Event Names:", unique_event_names)
except ValueError:
    print("Error parsing JSON response. Please check the API response format.")