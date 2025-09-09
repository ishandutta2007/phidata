"""Run `pip install ddgs sqlalchemy pgvector pypdf openai groq` to install dependencies."""

from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.models.groq import Groq
from agno.vectordb.pgvector import PgVector

db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"

knowledge = Knowledge(
    vector_db=PgVector(table_name="recipes", db_url=db_url),
)
# Add content to the knowledge
knowledge.add_content(
    url="https://agno-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf"
)

agent = Agent(
    model=Groq(id="llama-3.3-70b-versatile"),
    knowledge=knowledge,
)
agent.print_response("How to make Thai curry?", markdown=True)
