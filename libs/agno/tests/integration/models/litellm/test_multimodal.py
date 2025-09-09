from typing import Any

import requests

from agno.agent.agent import Agent
from agno.media import Audio, Image
from agno.models.litellm import LiteLLM
from agno.tools.duckduckgo import DuckDuckGoTools


def _get_audio_input() -> bytes | Any:
    """Fetch an example audio file and return it as base64 encoded string"""
    url = "https://openaiassets.blob.core.windows.net/$web/API/docs/audio/alloy.wav"
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def test_image_input():
    """Test LiteLLM with image input"""
    agent = Agent(
        model=LiteLLM(id="gpt-4o"),
        tools=[DuckDuckGoTools(cache_results=True)],
        markdown=True,
        telemetry=False,
    )

    response = agent.run(
        "Tell me about this image and give me the latest news about it.",
        images=[Image(url="https://upload.wikimedia.org/wikipedia/commons/0/0c/GoldenGateBridge-001.jpg")],
    )

    assert "golden" in response.content.lower()


def test_audio_input_bytes():
    """Test LiteLLM with audio input from bytes"""
    wav_data = _get_audio_input()

    # Provide the agent with the audio file and get result as text
    agent = Agent(
        model=LiteLLM(id="gpt-4o-audio-preview"),
        markdown=True,
        telemetry=False,
    )
    response = agent.run("What is in this audio?", audio=[Audio(content=wav_data, format="wav")])

    assert response.content is not None


def test_audio_input_url():
    """Test LiteLLM with audio input from URL"""
    agent = Agent(
        model=LiteLLM(id="gpt-4o-audio-preview"),
        markdown=True,
        telemetry=False,
    )

    response = agent.run(
        "What is in this audio?",
        audio=[Audio(url="https://openaiassets.blob.core.windows.net/$web/API/docs/audio/alloy.wav")],
    )

    assert response.content is not None


def test_single_image_simple():
    """Test LiteLLM with a simple image"""
    agent = Agent(
        model=LiteLLM(id="gpt-4o"),
        markdown=True,
        telemetry=False,
    )

    response = agent.run(
        "What do you see in this image?",
        images=[
            Image(url="https://upload.wikimedia.org/wikipedia/commons/0/0c/GoldenGateBridge-001.jpg"),
        ],
    )

    assert response.content is not None
    assert len(response.content) > 0
