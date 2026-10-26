import os
from openai import OpenAI
from anthropic import Anthropic
from groq import Groq

def get_llm_client(settings: dict):
    provider = settings.get("active_provider", "databricks")
    
    if provider == "databricks":
        host = settings.get("databricks_host", "https://dbc-10b9c2cb-e796.cloud.databricks.com")
        token = settings.get("databricks_token") or os.getenv("DATABRICKS_TOKEN", "")
        client = OpenAI(
            api_key=token,
            base_url=f"{host}/serving-endpoints",
            max_retries=3,
            timeout=120.0
        )
        model_name = settings.get("databricks_model") or "databricks-llama-4-maverick"
        return client, model_name, "openai"
        
    elif provider == "openai":
        token = settings.get("openai_api_key") or os.getenv("OPENAI_API_KEY", "")
        client = OpenAI(api_key=token)
        return client, "gpt-4o", "openai"
        
    elif provider == "groq":
        token = settings.get("groq_api_key") or os.getenv("GROQ_API_KEY", "")
        client = Groq(api_key=token)
        return client, "openai/gpt-oss-120b", "openai"
        
    elif provider == "anthropic":
        token = settings.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        client = Anthropic(api_key=token)
        return client, "claude-3-5-sonnet-20240620", "anthropic"
        
    raise ValueError(f"Unsupported provider: {provider}")

def call_llm(messages, tools, settings, stream=False):
    client, model, client_type = get_llm_client(settings)
    
    if client_type == "openai":
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
            "stream": stream
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            
        response = client.chat.completions.create(**kwargs)
        return response
    elif client_type == "anthropic":
        # Note: Anthropic uses a slightly different message format and tool format.
        # This is a basic mapping. In production, a unified layer like LiteLLM is preferred.
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m for m in messages if m["role"] != "system"]
        
        # Mapping OpenAI tools to Anthropic tools
        anthropic_tools = []
        if tools:
            for t in tools:
                anthropic_tools.append({
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"]
                })
        
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_msg,
            messages=user_msgs,
            tools=anthropic_tools if anthropic_tools else None
        )
        # Adapt response to openai format to keep rest of code simple
        # (This is simplified for illustration)
        class MockChoice:
            def __init__(self, message, finish_reason):
                self.message = message
                self.finish_reason = finish_reason
                
        class MockMessage:
            def __init__(self, content, tool_calls):
                self.content = content
                self.tool_calls = tool_calls
                
        class MockToolCall:
            def __init__(self, id, name, args):
                self.id = id
                self.type = "function"
                class MockFunc:
                    def __init__(self, n, a):
                        self.name = n
                        self.arguments = a
                self.function = MockFunc(name, args)

        content = ""
        tool_calls = []
        finish_reason = "stop"
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                import json
                tool_calls.append(MockToolCall(
                    id=block.id,
                    name=block.name,
                    args=json.dumps(block.input)
                ))
                finish_reason = "tool_calls"

        if stream:
            class MockDelta:
                def __init__(self, text, calls):
                    self.content = text
                    self.tool_calls = calls

            class MockStreamChunk:
                def __init__(self, delta):
                    self.choices = [type("Choice", (object,), {"delta": delta})()]

            streamed_calls = []
            for index, tool_call in enumerate(tool_calls):
                tool_call.index = index
                streamed_calls.append(tool_call)
            return iter([MockStreamChunk(MockDelta(content, streamed_calls))])
                
        return type('MockResponse', (object,), {
            "choices": [MockChoice(MockMessage(content, tool_calls), finish_reason)]
        })()

# --- LangGraph Multi-Agent Router ---
import operator
from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    active_agent: str
    next_step: str

def get_langgraph_app(settings):
    from langgraph.graph import StateGraph, END
    
    # Define Nodes (Manager, DAX, Semantic, RLS)
    def manager_node(state: AgentState):
        # Manager analyzes prompt and decides next step
        return {"active_agent": "manager", "next_step": "route"}
        
    def dax_agent_node(state: AgentState):
        return {"active_agent": "dax_agent", "next_step": "end"}
        
    def semantic_agent_node(state: AgentState):
        return {"active_agent": "semantic_agent", "next_step": "end"}
        
    def rls_agent_node(state: AgentState):
        return {"active_agent": "rls_agent", "next_step": "end"}
        
    def router_edge(state: AgentState) -> str:
        # Route based on manager's decision
        return "end" # placeholder for actual routing logic
        
    workflow = StateGraph(AgentState)
    
    workflow.add_node("manager", manager_node)
    workflow.add_node("dax_agent", dax_agent_node)
    workflow.add_node("semantic_agent", semantic_agent_node)
    workflow.add_node("rls_agent", rls_agent_node)
    
    workflow.set_entry_point("manager")
    workflow.add_conditional_edges("manager", router_edge, {
        "dax": "dax_agent",
        "semantic": "semantic_agent",
        "rls": "rls_agent",
        "end": END
    })
    
    workflow.add_edge("dax_agent", END)
    workflow.add_edge("semantic_agent", END)
    workflow.add_edge("rls_agent", END)
    
    return workflow.compile()
