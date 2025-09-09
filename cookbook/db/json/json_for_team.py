"""
<<<<<<< HEAD:cookbook/db/json/json_for_team.py
Use JSON files as the database for a Team.
Useful for simple demos where performance is not critical.

Run `pip install openai ddgs newspaper4k lxml_html_clean agno` to install the dependencies
=======
1. Run: `pip install openai ddgs newspaper4k lxml_html_clean agno` to install the dependencies
2. Run: `python cookbook/storage/yaml_storage/yaml_storage_for_team.py` to run the team
>>>>>>> 6901605678366bab6617a4cda9d874d8118bef13:cookbook/storage/yaml_storage/yaml_storage_for_team.py
"""

from typing import List

from agno.agent import Agent
from agno.db.json import JsonDb
from agno.models.openai import OpenAIChat
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.hackernews import HackerNewsTools
from pydantic import BaseModel

# Setup the JSON database
db = JsonDb(db_path="tmp/json_db")


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
    show_members_responses=True,
)

hn_team.print_response("Write an article about the top 2 stories on hackernews")
