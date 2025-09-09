import asyncio

from agno.agent import Agent, RunOutputEvent  # noqa
from agno.models.ibm import WatsonX

agent = Agent(
    model=WatsonX(id="mistralai/mistral-small-3-1-24b-instruct-2503"),
    debug_mode=True,
    markdown=True,
)

# Get the response in a variable
# run_response: Iterator[RunOutputEvent] = agent.run("Share a 2 sentence horror story", stream=True)
# for chunk in run_response:
#     print(chunk.content)

# Print the response in the terminal
asyncio.run(agent.aprint_response("Share a 2 sentence horror story", stream=True))
