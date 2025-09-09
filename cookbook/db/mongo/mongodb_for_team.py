"""
<<<<<<< HEAD:cookbook/db/mongo/mongodb_for_team.py
Use MongoDb as the database for a team.

Run `pip install openai ddgs newspaper4k lxml_html_clean agno` to install the dependencies
=======
1. Run: `pip install openai ddgs newspaper4k lxml_html_clean agno` to install the dependencies
2. Run: `python cookbook/storage/dynamodb_storage/dynamodb_storage_for_team.py` to run the team
>>>>>>> 6901605678366bab6617a4cda9d874d8118bef13:cookbook/storage/dynamodb_storage/dynamodb_storage_for_team.py
"""

from typing import List

from agno.agent import Agent
from agno.db.mongo import MongoDb
from agno.models.openai import OpenAIChat
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.hackernews import HackerNewsTools
from pydantic import BaseModel

# MongoDB connection settings
db_url = "mongodb://localhost:27017"
db = MongoDb(db_url=db_url)


class Article(BaseModel):
    title: str
    summary: str
    reference_links: List[str]


hn_researcher = Agent(
    name="HackerNews Researcher",
    model=OpenAIChat("gpt-4o"),
    role="Gets top stories from hackernews.",
    tools=[HackerNewsTools()],
)

web_searcher = Agent(
    name="Web Searcher",
    model=OpenAIChat("gpt-4o"),
    role="Searches the web for information on a topic",
    tools=[DuckDuckGoTools()],
    add_datetime_to_context=True,
)


hn_team = Team(
    name="HackerNews Team",
    model=OpenAIChat("gpt-4o"),
    members=[hn_researcher, web_searcher],
    db=db,
    instructions=[
        "First, search hackernews for what the user is asking about.",
        "Then, ask the web searcher to search for each story to get more information.",
        "Finally, provide a thoughtful and engaging summary.",
    ],
    output_schema=Article,
    markdown=True,
    debug_mode=True,
    show_members_responses=True,
    add_member_tools_to_context=False,
)

hn_team.print_response("Write an article about the top 2 stories on hackernews")
