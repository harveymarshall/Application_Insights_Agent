from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

import chainlit as cl
load_dotenv()

from langchain.tools import tool
import re

import re
from langchain_core.tools import tool

@tool
def extract_kql_query(query_response) -> str:
    """
    Extracts the KQL query from the response string or AIMessage.
    Removes markdown code blocks and returns the raw KQL.
    """
    # Handle LangChain AIMessage or dict
    if hasattr(query_response, "content"):
        text = query_response.content
    elif isinstance(query_response, dict) and "content" in query_response:
        text = query_response["content"]
    else:
        text = str(query_response)

    # Extract content inside triple backticks (with or without language tag)
    match = re.search(r"```(?:kql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: strip markdown markers manually and clean up
    text = re.sub(r"^(```kql|```)", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"(```)+$", "", text, flags=re.MULTILINE)
    text = text.strip()
    if "\\n" in text:
        cleaned_kql = text.replace("\\n", "\n")
    return cleaned_kql



def init_agent() -> create_react_agent:
    system_msg =  """
You are an expert in Azure Application Insights and fluent in Kusto Query Language (KQL). Your sole task is to convert user questions into valid KQL queries that can be executed against Application Insights logs.

Rules:
- Respond only with a KQL query.
- Do not ask the user for clarification.
- Do not include any natural language, comments, formatting, or explanations.
- If the question lacks specifics, make reasonable assumptions using standard Application Insights tables like `requests`, `traces`, `dependencies`, `exceptions`, and `customEvents`.

Your response must be a valid KQL query and nothing else.
"""
    agent = create_react_agent(
        model="openai:gpt-4o",
        tools=[extract_kql_query],
        prompt=system_msg
    )
    return agent


agent = init_agent()

@cl.on_message
async def chat(message: cl.Message):
    raw_response = agent.invoke({"role": "user", "content": message.content})
    # Extract the actual output string from the agent's response
    if isinstance(raw_response, dict) and "output" in raw_response:
        llm_response = raw_response["output"]
    else:
        llm_response = str(raw_response)
    cleaned_kql = extract_kql_query.invoke(llm_response)
    await cl.Message(content=f"```kql\n{cleaned_kql}\n```").send()



