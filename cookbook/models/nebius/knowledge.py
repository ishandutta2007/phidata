"""Run `pip install ddgs sqlalchemy pgvector pypdf cerebras_cloud_sdk` to install dependencies."""

from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.models.nebius import Nebius
from agno.vectordb.pgvector import PgVector

db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"

knowledge = Knowledge(
    vector_db=PgVector(table_name="recipes", db_url=db_url),
)
# Add content to the knowledge
knowledge.add_content(
    url="https://agno-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf"
)

agent = Agent(model=Nebius(id="Qwen/Qwen3-30B-A3B"), knowledge=knowledge)
agent.print_response("How to make Thai curry?", markdown=True)
