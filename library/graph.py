from json import loads, dumps, JSONDecodeError
from uuid import uuid4
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import AIMessage, ToolMessage
from src.main_logger import logger
from library.tools import (nl_sql_agent, execute_query, generate_highchart_config,
                           generate_dataset, get_llm_with_tools, nlp_to_chart)
from library.utils import trace_call, load_data_to_db, create_observation, get_tabel_mapping
from langgraph.graph.message import add_messages
from library.utils import extract_json_from_string

class State(TypedDict):
    llm_context: Annotated[list, add_messages]
    extra_context: dict
    session_id: str


graph_builder = StateGraph(State)


@trace_call
async def check_tools(state: State):
    try:
        logger.info("Checking for tool calls...")
        last_msg = state.get("llm_context")[-1]

        if isinstance(last_msg, AIMessage):
            try:
                _msg_content = extract_json_from_string(last_msg.content)
            except (JSONDecodeError, TypeError) as e:
                logger.info(f"Failed to parse last_msg.content as JSON: {e}")
                return END

            if all(key in _msg_content for key in ("action", "action_input")):
                logger.info(f"Found tool call: {_msg_content}")
                return "tools"

        logger.info("No tool calls found.")
    except Exception as e:
        logger.exception(f"check_tools error: {e}")

    return END


@trace_call
async def run_tools(state: State):
    try:
        last_msg = state["llm_context"][-1]
        _resp = extract_json_from_string(last_msg.content)
        _tool_call_id = str(uuid4())
        tool_name = _resp.get("action")
        tool_args = _resp.get("action_input", {})

        logger.info(f"Tool call: {tool_name} with args: {tool_args}")

        match tool_name:
            case "nl_sql_agent":
                tool_args["session_id"] = state["session_id"]
                _tool_args = dumps(tool_args)
                result = await nl_sql_agent.ainvoke((_tool_args))
                tool_resp = ToolMessage(content=create_observation(result), tool_call_id=_tool_call_id)
                state["llm_context"].append(tool_resp)

            case "execute_query":
                _tabel_mapping = get_tabel_mapping(state["session_id"])
                tool_args["tabel_mapping"] = _tabel_mapping
                _tool_args = dumps(tool_args)
                df, metadata = await execute_query.ainvoke(_tool_args)
                tool_resp = ToolMessage(content=create_observation(metadata), tool_call_id=_tool_call_id)
                state["llm_context"].append(tool_resp)
                if "error_message" not in metadata:
                    ref_key = metadata["ref_key"]
                    state["extra_context"][ref_key] = df

            case "generate_highchart_config":
                df_key = tool_args.pop("ref_key", "")
                df = state["extra_context"].get(df_key)
                if isinstance(df, dict):
                    tool_args["ref_key"] = df
                    chart_type = tool_args.get("chart_type","column")
                    ref_key, chart_config = await generate_highchart_config.ainvoke(tool_args)
                    state["extra_context"][ref_key] = chart_config
                    ref_key = f"{chart_type} chart created **chart ref**: {ref_key}"
                else:
                    ref_key = "Unable to generate chart at the moment"
                tool_resp = ToolMessage(content=create_observation(ref_key), tool_call_id=_tool_call_id)
                state["llm_context"].append(tool_resp)

            case "generate_dataset":
                result = generate_dataset.invoke(tool_args)
                if result.get("result"):
                    msg = load_data_to_db(result["result"], result["dataset_info"], state["session_id"])
                else:
                    msg = result.get("error", "unable to generate dataset at the moment")
                    msg += "<Instruction>Inform the user that you are currently unable to create a dataset.Politely suggest that they either upload an Excel file or allow you to attempt the task again.</Instruction>"
                tool_resp = ToolMessage(content=create_observation(msg), tool_call_id=_tool_call_id)
                state["llm_context"].append(tool_resp)

            case "nlp_to_chart":
                _user_ques = tool_args["question"]
                _args = {
                    "question":_user_ques,
                    "session_id": state["session_id"]
                }
                tool_args["question"] = dumps(_args)
                result = await nlp_to_chart.ainvoke(tool_args)
                if result["error"]:
                    msg = result["message"]
                else:
                    state["extra_context"][result["ref_key"]] = result["chart_config"]
                    msg = f"Chart generated sucessfully with ref key: {result['ref_key']}"
                tool_resp = ToolMessage(content=create_observation(msg), tool_call_id=_tool_call_id)
                state["llm_context"].append(tool_resp)
            case _:
                logger.warning("Unknown tool call received")

    except Exception as e:
        logger.info(f"run_tools error: {e}")
    return state


@trace_call
async def chat_bot(state: State):
    try:
        logger.info("---- extra_context ----")
        logger.info(state["extra_context"])
        logger.info("---- extra_context ----")

        logger.info(f"query for llm ==> {state['llm_context'][-1]}")
        llm = get_llm_with_tools()
        llm_resp = await llm.ainvoke(state["llm_context"])

        logger.info("---- llm_response ----")
        logger.info(llm_resp)
        logger.info("---- llm_response ----")

        state["llm_context"].append(llm_resp)
    except Exception as e:
        logger.info(f"chat_bot error: {e}")
    return state


# Build the graph
graph_builder.add_node("chatbot", chat_bot)
graph_builder.add_conditional_edges("chatbot", check_tools)
graph_builder.add_node("tools", run_tools)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)

graph = graph_builder.compile()


async def run_graph(state: State):
    """ Runs Graph """
    try:
        result = await graph.ainvoke(state)
    except Exception as e:
        logger.exception(f"error in running graph {e}")
        result = "We are ancountering an issue at our end Please Try again later"
    return result