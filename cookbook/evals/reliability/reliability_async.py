"""This example shows how to run a Reliability evaluation asynchronously."""

import asyncio
from typing import Optional

from agno.agent import Agent
from agno.eval.reliability import ReliabilityEval, ReliabilityResult
from agno.models.openai import OpenAIChat
from agno.run.agent import RunOutput
from agno.tools.calculator import CalculatorTools


def factorial():
    agent = Agent(
        model=OpenAIChat(id="gpt-4o-mini"),
        tools=[CalculatorTools()],
    )
    response: RunOutput = agent.run("What is 10!?")
    evaluation = ReliabilityEval(
        agent_response=response,
        expected_tool_calls=["factorial"],
    )

    # Run the evaluation calling the arun method.
    result: Optional[ReliabilityResult] = asyncio.run(
        evaluation.arun(print_results=True)
    )
    if result:
        result.assert_passed()


if __name__ == "__main__":
    factorial()
