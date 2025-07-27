import functools
import re
from ast import literal_eval
import time
from datetime import datetime
import sqlite3
import asyncio
from json import dumps
import pandas as pd
from json import loads
from uuid import uuid4
from library.db_connect import session_scope
from library.models import Dataset, ChatThread
from src.main_logger import logger

def trace_call(func):
    """ Traces function Entry Exit and Time, supports sync and async funcs """

    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.info(f"====================== 🔷 Entering: {func.__name__} Node =====================")
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"=============== ✅ Exiting: {func.__name__} (Execution time: {duration:.4f} seconds)======")
            return result
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger.info(f"====================== 🔷 Entering: {func.__name__} Node =====================")
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"=============== ✅ Exiting: {func.__name__} (Execution time: {duration:.4f} seconds)======")
            return result
        return sync_wrapper



def extract_json_from_string(s: str):
    """
    Extracts the first valid JSON object from a string.

    Returns:
        The parsed JSON object (as dict or list), or None if not found.
    """
    output = {}
    try:
        start = 0
        end = len(s)-1
        while(start<end):
            if s[start] == "{":
                break
            start +=1
        while(end>start):
            if s[end] == "}":
                break
            end -=1
        output = loads(s[start:end+1])
    except Exception as e:
        logger.exception(f'error while extracting json {e}')
        output = literal_eval(s[start:end+1])
    return output



def get_table_ddl(actual_table, table_alias):
    """Gets the table ddl from db"""
    try:
        conn = sqlite3.connect("local_db.sqlite")
        cursor = conn.cursor()

        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (actual_table,))
        ddl = cursor.fetchone()

        conn.close()
        _ddl = ddl[0] if ddl else None
        if _ddl:
            _ddl = _ddl.replace(actual_table, table_alias)
            logger.info(f"ddl after replacing tabel name with aliasing \n{_ddl}")
            return _ddl
    except Exception as e:
        logger.exception(f"error in getting DDL {e}")


def save_dataset_info(ddls, metadata, tabel_mapping, session_id):
    _result = ""
    try:
        dataset_metadata = {
            "ddls":ddls,
            "tabel_mapping":tabel_mapping
        }
        new_dataset = Dataset(
            name = metadata.get("dataset_name","sampel data"),
            description = metadata.get("description",""),
            dataset_metadata = dataset_metadata,
            created_by = session_id
        )

        with session_scope() as session:
            session.add(new_dataset)
            session.commit()
            session.refresh(new_dataset)
            _dataset_id = new_dataset.dataset_id
            chat_thread = session.query(ChatThread).filter(
                ChatThread.session_uuid == session_id,
                ChatThread.is_active == True
            ).first()
            chat_thread.dataset_id = _dataset_id
            session.commit()

            msg = {
                "table_ddls":ddls,
                "dataset_info": metadata,
                "status":"Created sucessfully",
                "hint":"kindly give detailed info to user about dataset in points"
            }
            _result = dumps(msg)
    except Exception as e:
        logger.exception(f"error in saving ddls to firebase: {e}")
        _result = "unable to update dataset info in db"
    return _result

def load_data_to_db(data, metadata, session_id):
    """Dums df to sql lite tables"""
    tabel_ddls = {}
    tabel_mapping = {}
    msg = ""
    try:
        conn = sqlite3.connect("local_db.sqlite")
        for tabel_name, df in data.items():
            __table = str(uuid4()).replace('-', '_')
            df.to_sql(__table, conn, index=False, if_exists="fail")
            logger.info(f"Data dumped in table {__table} for {tabel_name}")
            tabel_ddl = get_table_ddl(__table, tabel_name)
            tabel_ddls[tabel_name] = tabel_ddl
            tabel_mapping[tabel_name.lower()] = __table
        logger.info("Data load completed sucessfully")
        msg =  save_dataset_info(tabel_ddls, metadata, tabel_mapping, session_id)
    except Exception as e:
        logger.exception(f"error in loading data to db {e}")
        msg = f"error in loading data to db {e}\npolitely inform this to user and also ask him to create dataset by uploading excel or try again in some time"
    finally:
        conn.close()
    return msg

def create_observation(msg):
    """doc str"""
    try:
        msg = dumps({"Observation":msg})
    except Exception as e:
        logger.exception(f"error in creating thought response {e}")
    return msg



def remove_imports(code: str) -> str:
    """
    Removes all import statements from a Python code string.
    Handles both 'import ...' and 'from ... import ...'.
    """
    try:

        # Regex to match lines starting with import or from ... import
        return re.sub(r'^\s*(?:import\s+[^\n]+|from\s+\S+\s+import\s+[^\n]+)\n?', '', code, flags=re.MULTILINE)
    except Exception as e:
        logger.exception(f"error in removing imports from generated code {e}")
        return code


def format_ddls(ddls: dict) -> str:
    """
    Takes a dictionary of table DDLs and returns a formatted string for appending to a prompt.

    Args:
        ddls (dict): A dictionary where keys are table names and values are DDL strings.

    Returns:
        str: A formatted string with DDLs in the desired format.
    """
    resut = ""
    try:
        formatted_text = []

        for table_name, ddl in ddls.items():
            formatted_text.append(f"-- DDL for table `{table_name}`\n{ddl.strip()}\n")

        resut =  "\n".join(formatted_text)

    except Exception as e:
        logger.exception(f"Error formatting DDLs: {str(e)}")
    return resut


def get_ddls(session_id):
    """Fetch DDLS"""
    ddls = {}
    try:
        from sqlalchemy.dialects import mysql
        with session_scope() as session:
            _metadata = session.query(
                Dataset.dataset_metadata
            ).join(
                ChatThread, Dataset.dataset_id == ChatThread.dataset_id
            ).filter(
                ChatThread.session_uuid == session_id
            ).scalar()

        logger.info("*"*20)
        logger.info(f"dataset_metadata {_metadata}")
        logger.info("*"*20)

        if _metadata:
            ddls = _metadata.get("ddls",{})
    except Exception as e:
        logger.exception(f"error in fetching ddls {e}")
    return ddls

def get_tabel_mapping(session_id):
    """Fetch tabel mapping"""
    mapping = {}
    try:
        with session_scope() as session:
            _metadata = session.query(
                Dataset.dataset_metadata
            ).join(
                ChatThread, Dataset.dataset_id == ChatThread.dataset_id
            ).filter(
                ChatThread.session_uuid == session_id
            ).scalar()
        if _metadata:
            mapping = _metadata.get("tabel_mapping", {})
    except Exception as e:
        logger.exception(f"error in fetching ddls {e}")
    return mapping


def resolve_tags(input_str: str) -> str:
    """Resolves nested tags"""
    try:
        # --- Rule 0: Wrap entire string in <text> if no tags are present ---
        if not re.search(r'<(text|sql|chart)>', input_str):
            return f"<text>{input_str}</text>"

        # --- Rule 1: Ensure <sql> is inside <text> ---
        input_str = re.sub(
            r'<text>(.*?)</text>\s*<sql>(.*?)</sql>',
            r'<text>\1<sql>\2</sql></text>',
            input_str,
            flags=re.DOTALL
        )

        # --- Rule 2: Place <chart> directly after <text> ---
        def extract_chart_inside_text(m):
            text_content = re.sub(r'<chart>.*?</chart>', '', m.group(1))
            chart_content = re.findall(r'<chart>.*?</chart>', m.group(1))
            if chart_content:
                return f"<text>{text_content}</text>{''.join(chart_content)}"
            return m.group(0)

        input_str = re.sub(r'<text>(.*?)</text>', extract_chart_inside_text, input_str, flags=re.DOTALL)

    except Exception as e:
        logger.exception(f"error in resolving tags {e}")

    return input_str
