import multiprocessing
import re
import asyncio
import traceback
import sqlite3
import pandas as pd
from typing import Any
from json import dumps, loads
import numpy as np
from faker import Faker
from uuid import uuid4
import pandas as pd
from langchain_core.messages import  HumanMessage, SystemMessage
from langchain_core.tools import tool
from library.utils import (trace_call, extract_json_from_string, get_ddls, format_ddls,
                            get_tabel_mapping, remove_imports)
from src.main_logger import logger
from library.prompts import NL_SQL_PROMPT, CODE_GENERATOR_PROMPT, CHART_INPUT_PROMPT
from library.llm_resp import llm, llm_complex
from library.resolve_sql import replace_table_names



@tool
@trace_call
async def execute_query(query: str) -> dict:
    """
    Executes a SQL query on a SQLite database and returns the result metadata.

    Parameters:
    - query (str): SQL query to execute.

    Returns:
    - metadata (dict): keys:
        rows-> count of rows in df,
        columns -> column information in df,
        ref_key -> uuid4 This can be used as a refrence to other functions in place of actual data
    Note: In case of error a error_message key will only be present in the dict
        containing error message
    """
    def run_query(_sql):
        try:
            conn = sqlite3.connect("local_db.sqlite")
            df = pd.read_sql_query(_sql, conn)
            conn.close()

            ref_key = str(uuid4())
            metadata = {
                "rows": len(df),
                "columns": list(df.columns),
                "ref_key": ref_key
            }
            df_dict = df.to_dict(orient='list')
            return df_dict, metadata

        except Exception as e:
            return {}, {
                "error_message": f"An error occurred during data fetching: {e}"
            }
    _args = loads(query)
    _query = _args.get("query")
    tabel_mapping = _args.get("tabel_mapping",{})
    resolved_sql = replace_table_names(_query, tabel_mapping)
    logger.info(f"sql query after resolution {resolved_sql}")
    return await asyncio.to_thread(run_query, resolved_sql)


@tool
@trace_call
async def nl_sql_agent(question: str) -> str:
    """
    Converts a natural language question into an SQLite-compatible SQL query
    - Should only be used to generate sql queries
    """
    try:
        _params = loads(question)
        _ques = _params.get("question","")
        session_id = _params.get("session_id")
        ddls = await asyncio.to_thread(get_ddls, session_id)
        tabel_text = format_ddls(ddls)
        logger.info(f"Args: {question=}")
        logger.info(f"tabel DDLS ---\n {tabel_text}\n-----------")
        _prompt = NL_SQL_PROMPT.format(ddls=tabel_text)
        messages = [
            SystemMessage(content=_prompt),
            HumanMessage(content=_ques)
        ]

        llm_resp = await llm_complex.ainvoke(messages)
        logger.info(f"nl_sql_agent Response: {llm_resp}")

        def extract_sql():
            think_match = re.search(r"<think>(.*?)</think>", llm_resp.content, re.DOTALL)
            think_content = think_match.group(1).strip() if think_match else ""
            cleaned = re.sub(r"<think>.*?</think>", "", llm_resp.content, flags=re.DOTALL)
            return cleaned.strip()

        cleaned_string = await asyncio.to_thread(extract_sql)

        logger.info(f"-----------SQL generated: \n{cleaned_string} -------------")
        return cleaned_string

    except Exception as e:
        logger.exception(e)
        return "Could not generate sql query"

@tool
@trace_call
async def generate_highchart_config(ref_key: str|Any, x: str, y: str, chart_type: str, chart_title: str) -> str:
    """
    Creates a high chart config
    Input:
        ref_key: the output key to refrence data (uuid4 you get by execute query tool)
        x: Column to be used in x axis of chart (should match actual column name in data)
        y: Column to be used in y axis of chart (should match actual column name in data)
        chart_type: chart type to display (e.g. bar, column, line, area, pie etc)
        chart_title: chart title to be displayed on the chart
    Returns:
        uuid4 string which can be given to user as output
    """
    def _generate():
        try:
            if not isinstance(ref_key.get(x), list) or not isinstance(ref_key.get(y), list):
                raise ValueError("Unable to access column data")
            if len(ref_key[x]) != len(ref_key[y]):
                raise ValueError("x and y columns must be of the same length")

            _columns = list(ref_key.keys())
            logger.info(_columns)

            chart_type_local = chart_type or "line"
            chart_title_local = chart_title or "Chart Generated"

            if x not in _columns or y not in _columns:
                raise ValueError("Specified x or y column does not exist in the input data")

            logger.info(f"{chart_title_local=}")
            logger.info(f"{x=} {y=} {chart_type_local=}")

            data = [{"x": i, "y": float(val)} for i, val in enumerate(ref_key[y])]
            categories = [str(val) for val in ref_key[x]]

            config = {
                "chart": {
                    "type": chart_type_local,
                    "zoomType": "xy"
                    # "scrollablePlotArea": {
                    #     "minWidth": 700,
                    #     "minHeight": 400,
                    #     "scrollPositionX": 1,
                    #     "scrollPositionY": 1
                    # }
                },
                "title": {"text": chart_title_local},
                "xAxis": {
                    "categories": categories,
                    "max": 9 if len(categories) > 10 else None,
                    "scrollbar": {"enabled": len(categories) > 10},
                    "scrollbar": {"enabled": True},
                    "title": {"text": x},
                    "min": 0
                },
                "yAxis": {
                    "title": {"text": y},
                    "scrollbar": {"enabled": True}
                },
                "legend": {"enabled": True},
                "tooltip": {
                    "shared": True,
                    "crosshairs": True,
                    "valueDecimals": 2
                },
                "series": [{
                    "name": y,
                    "data": data,
                    "marker": {"enabled": True}
                }],
                "plotOptions": {
                    chart_type_local: {
                        "marker": {"enabled": True},
                        "dataLabels": {"enabled": False}
                    }
                },
                "credits": {"enabled": False},
                "responsive": {
                    "rules": [{
                        "condition": {"maxWidth": 500},
                        "chartOptions": {
                            "legend": {
                                "layout": "horizontal",
                                "align": "center",
                                "verticalAlign": "bottom"
                            }
                        }
                    }]
                }
            }

            return str(uuid4()), config

        except Exception as e:
            logger.exception("Failed to generate chart config:")
            return f"unable to generate chart config ERROR: {e}", {"error_message": True}
    return await asyncio.to_thread(_generate)


def _execute_code(code, variables_to_return, return_dict):
    try:
        fake = Faker()
        allowed_globals = {
            "__builtins__":{
            # Basic types and constructors
            "range": range,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,

            # Iteration and functional programming
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "any": any,
            "all": all,

            # Numeric utilities
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "pow": pow,

            # String utilities
            "format": format,
            "chr": chr,
            "ord": ord,
        },
            "pd": pd,
            "np": np,
            "faker": fake,
            "Faker": Faker,
        }

        local_vars = {}
        exec(code, allowed_globals, local_vars)
        if variables_to_return:
            output = {var: local_vars.get(var, None) for var in variables_to_return}
        else:
            output = local_vars
        return_dict["result"] = output

    except Exception:
        return_dict["error"] = traceback.format_exc()


def run_code(code: str, variables_to_return: list = None, timeout: int = 7):

    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    p = multiprocessing.Process(target=_execute_code, args=(code, variables_to_return, return_dict))
    p.start()
    p.join(timeout)

    if p.is_alive():
        p.terminate()
        return {"error": f"Code execution exceeded {timeout} seconds."}

    return dict(return_dict)


@tool
@trace_call
def generate_dataset(user_request:str) -> str:
    """
    Generates a Synthetic Dataset
    Input: takes a user request to create  a Dataset
    Never call this tool unless user explicitly ask you to create a dataset
    """
    try:
        messages = [
            SystemMessage(content=CODE_GENERATOR_PROMPT),
            HumanMessage(content=user_request)
        ]

        llm_resp = llm_complex.invoke(messages)
        think_content_match = re.search(r"<think>(.*?)</think>", llm_resp.content, re.DOTALL)
        code_match = re.search(r"<code>(.*?)</code>", llm_resp.content, re.DOTALL)
        json_match = re.search(r"<json>(.*?)</json>", llm_resp.content, re.DOTALL)
        think_content = think_content_match.group(1).strip() if think_content_match else ""
        cleaned_string = re.sub(r"<think>.*?</think>", "", llm_resp.content, flags=re.DOTALL)
        code = code_match.group(1).strip() if code_match else ""
        _json_candidate = json_match.group(1).strip() if json_match else ""
        logger.info(f"code--\n{code}\njson-\n{_json_candidate}")
        json_resp = extract_json_from_string(_json_candidate)
        logger.info(f"----------------\n{json_resp}\n-------------------")
        vars = json_resp.pop("vars",[])
        logger.info(f"variables to acess --> {vars}")
        code = remove_imports(code)
        result = run_code(code, vars)
        print("*"*40)
        print(result)
        print("*"*40)
        result["dataset_info"] = json_resp
        if "error" in result:
            logger.info("retring ....")
            messages.append(HumanMessage(f"from your given code i ancountered below error:\n{result.get('error','')}\n\nPlease fix it and regenerate complete json object and nothing else"))
            _fixed_error = llm_complex.invoke(messages)
            think_content = think_content_match.group(1).strip() if think_content_match else ""
            cleaned_string = re.sub(r"<think>.*?</think>", "", _fixed_error.content, flags=re.DOTALL)
            code_match = re.search(r"<code>(.*?)</code>", _fixed_error.content, re.DOTALL)
            json_match = re.search(r"<json>(.*?)</json>", _fixed_error.content, re.DOTALL)
            _code = code_match.group(1).strip() if code_match else ""
            _json_candidate = json_match.group(1).strip() if json_match else ""
            logger.info(cleaned_string)
            _fixed_error = extract_json_from_string(_json_candidate)
            _code = remove_imports(_code)
            _vars = _fixed_error.pop("vars",[])
            result = run_code(_code, _vars)
            logger.info(f"output after fix")
            print("*"*40)
            print(result)
            print("*"*40)
            result["dataset_info"] = _fixed_error
        return result
    except Exception  as e:
        logger.exception(f"error in geerate dataset {e}")
        return {"error":"Unable to create dataset at the moment"}

@tool
@trace_call
async def nlp_to_chart(question:str, chart_type:str|None)->str:
    """
    Takes a user question and provides appropriate chart if possible to make
    chart type should only be filled if the user asks for a specific chart
    if not possible returns the appropriate reason for not creating chart
    """
    try:
        _input = loads(question)
        session_id = _input.get("session_id")
        sql_pattern = r"<sql>(.*?)</sql>"
        query = ""
        logger.info(f"calling nlp to sql agent ")
        response = await nl_sql_agent.ainvoke(question)
        query_list = re.findall(sql_pattern, response, re.DOTALL)
        if len(query_list) == 1 and query_list[0].strip():
            query = query_list[0]
        else:
            return response
        _tabel_mapping = get_tabel_mapping(session_id)
        _query_args = {
            "query":query,
            "tabel_mapping":_tabel_mapping
        }
        _query_args = dumps(_query_args)
        data, metadata = await execute_query.ainvoke(_query_args)
        if "error_message" in metadata:
            return metadata["error_message"]
        metadata.pop("ref_key",None)
        _chart_prompt = [
            SystemMessage(content=CHART_INPUT_PROMPT),
            HumanMessage(content=dumps(metadata))
        ]
        resp = await llm_complex.ainvoke(_chart_prompt)
        logger.info(f"chart input response {resp.content}")
        charting_input = extract_json_from_string(resp.content)
        charting_input["ref_key"] = data
        charting_input["chart_type"] = chart_type
        chart_ref_key, chart_config = await generate_highchart_config.ainvoke(charting_input)
        return {"ref_key": chart_ref_key, "chart_config": chart_config, "error":False}
    except Exception as e:
        logger.exception(f"error in nlp to chart tool {e}")
        return {"error":True, "message":'unable to generate chart at the momment'}

def get_llm_with_tools():
    """Returns llm with tools"""
    tools = [nl_sql_agent, execute_query, generate_highchart_config, generate_dataset, nlp_to_chart]
    llm_with_tools = llm.bind_tools(tools=tools, tool_choice="auto")
    return llm_with_tools

if __name__ == "__main__":
    code = """

"""
    result = run_code(code, variables_to_return=["df"])
    df = result.get("result", {}).get("df")

    if "error" in result:
        logger.info("Error:", result["error"])
    elif df is not None:
        logger.info(df)
    else:
        logger.info("No DataFrame returned.")
