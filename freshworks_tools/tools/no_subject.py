import os
import requests
from urllib.parse import urlparse, parse_qs
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import json
from litellm import completion
import base64
from PIL import Image

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

        render_url = f"{parsed_url.scheme}://{parsed_url.netloc}/render/d/{dashboard_uid}/{dashboard_slug}?orgId={org_id}&from=now-1h&to=now&width=1000&height=500"
        return render_url, org_id
    except (IndexError, ValueError) as e:
        print(f"Invalid Grafana dashboard URL: {str(e)}")
        raise

def download_grafana_image(render_url, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(render_url, headers=headers)
    if response.status_code == 200:
        filename = "grafana_dashboard.png"
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"Grafana dashboard image downloaded successfully: {filename}")
        return filename
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

def analyze_image_with_vision_model(image_path):
    # Open the image
    image = Image.open(image_path)

    # Resize the image (e.g., to 800x800)
    image = image.resize((800, 800))

    # Save the resized image
    image.save(image_path)

    # Encode the image
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    llm_key = os.environ["VISION_LLM_KEY"]
    llm_base_url = os.environ["VISION_LLM_BASE_URL"]

    # openai call
    try:
        response = completion(
            model="openai/gpt-4o",
            api_key=llm_key,
            base_url=llm_base_url,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this Grafana dashboard image. Identify any abnormalities or significant patterns in the data. Provide a brief summary of your observations."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
    except Exception as e:
        print(f"Error for llm: {e}")
        return "Unable to analyze the image due to an error."

    try:
        return response.choices[0].message.content
    except Exception as e:
        print(f"Failed to get content from response: {e}")
        return "Unable to analyze the image due to an error."

def main():
    # Access environment variables
    grafana_dashboard_url = os.environ.get("GRAFANA_DASHBOARD_URL")
    thread_ts = os.environ.get("SLACK_THREAD_TS")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")
    slack_token = os.environ.get("SLACK_API_TOKEN")
    grafana_api_key = os.environ.get("GRAFANA_API_KEY")

    # Generate Grafana render URL
    render_url, org_id = generate_grafana_render_url(grafana_dashboard_url)
    print(f"Generated Grafana render URL: {render_url}")

    # Download Grafana image
    image_path = download_grafana_image(render_url, grafana_api_key)

    # Analyze the image using the vision model
    analysis_result = analyze_image_with_vision_model(image_path)

    # Send image to Slack thread
    initial_comment = (f"Grafana dashboard image from: {grafana_dashboard_url}\n\n"
                       f"Analysis:\n{analysis_result}")
    slack_response = send_slack_file_to_thread(slack_token, channel_id, thread_ts, image_path, initial_comment)

    # Extract relevant information from the Slack response
    response_info = extract_slack_response_info(slack_response)
    print("Slack response:")
    print(json.dumps(response_info, indent=2))

    # Clean up the downloaded image
    os.remove(image_path)
    print("Temporary image file removed")

    print("Processing complete")

if __name__ == "__main__":
    main()