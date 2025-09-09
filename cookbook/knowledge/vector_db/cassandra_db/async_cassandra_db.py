import asyncio

from agno.agent import Agent
from agno.knowledge.embedder.mistral import MistralEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.models.mistral import MistralChat
from agno.vectordb.cassandra import Cassandra

try:
    from cassandra.cluster import Cluster  # type: ignore
except (ImportError, ModuleNotFoundError):
    raise ImportError(
        "Could not import cassandra-driver python package.Please install it with pip install cassandra-driver."
    )

cluster = Cluster()

session = cluster.connect()
session.execute(
    """
    CREATE KEYSPACE IF NOT EXISTS testkeyspace
    WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 1 }
    """
)

knowledge = Knowledge(
    vector_db=Cassandra(
        table_name="recipes",
        keyspace="testkeyspace",
        session=session,
        embedder=MistralEmbedder(),
    ),
)

agent = Agent(
    model=MistralChat(),
    knowledge=knowledge,
)

if __name__ == "__main__":
    # Comment out after first run
    asyncio.run(
        knowledge.add_content_async(url="https://docs.agno.com/introduction/agents.md")
    )

    # Create and use the agent
    asyncio.run(
        agent.aprint_response(
            "What is the purpose of an Agno Agent?",
            markdown=True,
        )
    )
