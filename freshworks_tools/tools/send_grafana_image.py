from kubiya_sdk.tools import Arg, FileSpec
from .base import FreshworksTool
from kubiya_sdk.tools.registry import tool_registry
import inspect

from . import grafana

old_tool = FreshworksTool(
    name="old_tool",
    description="Old tool",
    content="""
    # Debug: Print the passed arguments
    if [ -z $grafana_dashboard_url ]; then
        echo "Error: 'grafana_dashboard_url' is not set or empty"
    else
        echo "Passed grafana_dashboard_url: $grafana_dashboard_url"
    fi
    
    # Set environment variables
    export GRAFANA_URL=$grafana_dashboard_url
    echo "GRAFANA_URL: $GRAFANA_URL"
    echo "THREAD_TS: $SLACK_THREAD_TS"
    echo "CHANNEL_ID: $SLACK_CHANNEL_ID"
    
    # Install required Python packages
    pip install --root-user-action ignore -q requests slack_sdk

    # Run the Python script to generate the Grafana render URL, download the image, and send it to the Slack thread
    python -c '
import os
import requests
from urllib.parse import urlparse, parse_qs
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json

def generate_grafana_render_url(grafana_dashboard_url):
    print(f"Received Grafana URL: {grafana_dashboard_url}")
    parsed_url = urlparse(grafana_dashboard_url)
    path_parts = parsed_url.path.strip("/").split("/")

    try:
        if len(path_parts) >= 3 and path_parts[0] == "d":
            dashboard_uid = path_parts[1]
            dashboard_slug = path_parts[2]
        else:
            raise ValueError("URL path does not have the expected format /d/{uid}/{slug}")

        query_params = parse_qs(parsed_url.query)
        org_id = query_params.get("orgId", ["1"])[0]

        render_url = f"{parsed_url.scheme}://{parsed_url.netloc}/render/d-solo/{dashboard_uid}/{dashboard_slug}?orgId={org_id}&from=now-1h&to=now&panelId=1&width=1000&height=500"
        return render_url
    except (IndexError, ValueError) as e:
        print(f"Invalid Grafana dashboard URL: {str(e)}")
        raise

def download_grafana_image(render_url, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(render_url, headers=headers)
    if response.status_code == 200:
        with open("grafana_dashboard.png", "wb") as f:
            f.write(response.content)
        print("Grafana dashboard image downloaded successfully")
        return "grafana_dashboard.png"
    else:
        print(f"Failed to download Grafana image. Status code: {response.status_code}")
        raise Exception("Failed to download Grafana image")

def send_slack_file_to_thread(token, channel_id, thread_ts, file_path, initial_comment):
    client = WebClient(token=token)
    try:
        response = client.files_upload_v2(
            channel=channel_id,
            file=file_path,
            initial_comment=initial_comment,
            thread_ts=thread_ts
        )
        return response
    except SlackApiError as e:
        print(f"Error sending file to Slack thread: {e}")
        raise

def extract_slack_response_info(response):
    return {
        "ok": response.get("ok"),
        "file_id": response.get("file", {}).get("id"),
        "file_name": response.get("file", {}).get("name"),
        "file_url": response.get("file", {}).get("url_private"),
        "timestamp": response.get("file", {}).get("timestamp")
    }

# Access environment variables
grafana_dashboard_url = os.environ.get("GRAFANA_URL")
thread_ts = os.environ.get("SLACK_THREAD_TS")
channel_id = os.environ.get("SLACK_CHANNEL_ID")
slack_token = os.environ.get("SLACK_API_TOKEN")
grafana_api_key = os.environ.get("GRAFANA_API_KEY")

# Generate Grafana render URL
render_url = generate_grafana_render_url(grafana_dashboard_url)
print(f"Generated Grafana render URL: {render_url}")

# Download Grafana image
image_path = download_grafana_image(render_url, grafana_api_key)

# Send image to Slack thread
initial_comment = f"Grafana dashboard image from: {grafana_dashboard_url}"
slack_response = send_slack_file_to_thread(slack_token, channel_id, thread_ts, image_path, initial_comment)

# Extract relevant information from the Slack response
response_info = extract_slack_response_info(slack_response)
print("Slack response:")
print(json.dumps(response_info, indent=2))

# Clean up the downloaded image
os.remove(image_path)
print("Temporary image file removed")
' """,
    args=[
        Arg(
            name="grafana_dashboard_url",
            type="str",
            description="URL of the Grafana dashboard",
            required=True
        )
    ]
)

get_grafana_image_and_send_slack_thread = FreshworksTool(
    name="get_grafana_image_and_send_slack_thread",
    description="Generate render URLs for relevant Grafana dashboard panels, download images, analyze them using OpenAI's vision model, and send results to the current Slack thread",
    type="docker",
    image="python:3.11-bullseye",
    content="""
pip install requests slack_sdk litellm > /dev/null 2>&1

python /tmp/grafana.py --grafana_dashboard_url "$grafana_dashboard_url" --alert_subject "$alert_subject"
""",
    secrets=[
        "SLACK_API_TOKEN", 
        "GRAFANA_API_KEY", 
        "OPENAI_API_KEY"
    ],
    env=[
        "SLACK_THREAD_TS", 
        "SLACK_CHANNEL_ID", 
        "OPENAI_API_BASE"
    ],
    args=[
        Arg(
            name="grafana_dashboard_url",
            type="str",
            description="URL of the Grafana dashboard",
            required=True
        ),
        Arg(
            name="alert_subject",
            type="str",
            description="Subject of the alert, used to filter relevant panels",
            required=True
        )
    ],
    with_files=[
        FileSpec(
            destination="/tmp/grafana.py",
            source=inspect.getsource(grafana)
        )
    ]
)

# Register the updated tool
tool_registry.register("freshworks", old_tool)
tool_registry.register("freshworks", get_grafana_image_and_send_slack_thread)