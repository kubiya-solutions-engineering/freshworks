import inspect

from kubiya_sdk import tool_registry
from kubiya_sdk.tools.models import Arg, Tool, FileSpec

from . import grafana

get_grafana_image_and_send_slack_thread = Tool(
    name="get_grafana_image_and_send_slack_thread",
    description="Generate render URLs for relevant Grafana dashboard panels, download images, analyze them using OpenAI's vision model, and send results to the current Slack thread",
    type="docker",
    image="python:3.11-bullseye",
    content="""
pip install slack_sdk requests==2.32.3 litellm==1.49.5 pillow==11.0.0 > /dev/null 2>&1

python /tmp/grafana.py --grafana_dashboard_url "$grafana_dashboard_url" --alert_subject "$alert_subject"
""",
    secrets=[
        "SLACK_API_TOKEN", 
        "GRAFANA_API_KEY", 
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "VISION_LLM_KEY"
    ],
    env=[
        "SLACK_THREAD_TS", 
        "SLACK_CHANNEL_ID",
        "VISION_LLM_BASE_URL"
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
tool_registry.register("freshworks", get_grafana_image_and_send_slack_thread)