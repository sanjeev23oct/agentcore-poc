"""
Minimal Bedrock AgentCore POC: one agent, one tool, deployed to AgentCore Runtime.

Local test:
    python agent.py
    -> starts a local server, then:
    curl -X POST http://localhost:8080/invocations \
        -H "Content-Type: application/json" \
        -d '{"prompt": "What is 12 * 7?"}'

Deploy:
    agentcore configure --entrypoint agent.py
    agentcore launch
"""

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool

app = BedrockAgentCoreApp()


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '12 * 7'."""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


agent = Agent(
    model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    tools=[calculator],
    system_prompt="You are a concise assistant. Use the calculator tool for any math.",
)


@app.entrypoint
def invoke(payload: dict):
    prompt = payload.get("prompt", "")
    result = agent(prompt)
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
