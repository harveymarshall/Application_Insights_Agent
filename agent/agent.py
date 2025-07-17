from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv

import chainlit as cl
load_dotenv()

from langchain.tools import tool
import re

import re
from langchain_core.tools import tool
import httpx

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

# Store conversation state
user_states = {}

@cl.on_message
async def chat(message: cl.Message):
    user_id = message.author  # Or another unique identifier
    state = user_states.get(user_id, {})

    if "awaiting_confirmation" in state and state["awaiting_confirmation"]:
        # User is confirming the KQL query
        if message.content.strip().lower() in ["yes", "y"]:
            # Send KQL to MCP server
            kql_query = state["kql_query"]
            app_id = "YOUR_APP_ID"
            api_key = "YOUR_API_KEY"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/query",
                    json={"kql_query": kql_query, "app_id": app_id, "api_key": api_key}
                )
            if response.status_code == 200:
                result = response.json()
                await cl.Message(content=f"Results:\n{result}").send()
            else:
                await cl.Message(content=f"Error: {response.text}").send()
            user_states[user_id] = {}  # Reset state
        else:
            await cl.Message(content="Okay, please provide a new question or modify your query.").send()
            user_states[user_id] = {}
        return

    # Step 1: User asks a question, agent generates KQL
    raw_response = agent.invoke({"role": "user", "content": message.content})
    if isinstance(raw_response, dict) and "output" in raw_response:
        kql_query = raw_response["output"]
    else:
        kql_query = str(raw_response)
    cleaned_kql = extract_kql_query.invoke(kql_query)
    user_states[user_id] = {"awaiting_confirmation": True, "kql_query": cleaned_kql}
    await cl.Message(content=f"```kql\n{cleaned_kql}\n```\n\nDoes this query look sensible? (yes/no)").send()



