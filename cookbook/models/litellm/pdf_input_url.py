from agno.agent import Agent
from agno.media import File
from agno.models.litellm import LiteLLM

agent = Agent(
    model=LiteLLM(id="gpt-4o"),
    markdown=True,
    add_history_to_context=True,
)

agent.print_response(
    "Suggest me a recipe from the attached file.",
    files=[File(url="https://agno-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf")],
)
