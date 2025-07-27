from fastapi import APIRouter, Request, BackgroundTasks
from datetime import datetime
import asyncio
import re
from json import loads, dumps
from langchain_core.messages.utils import messages_from_dict
from src.main_logger import logger
from library.cache_connect import get_redis
from library.db_connect import session_scope
from library.models import ChatThread, ChatMessage
from library.prompts import MASTER_SYSTEM_PROMOPT, ONE_SHOT, NO_DATASET
from src.data_models import QueryPayload
from library.graph import run_graph
from library.utils import resolve_tags

router = APIRouter()


def add_chat_thread(session_id):
    """New Chat Thread"""
    try:
        thread_id = None
        new_thread = ChatThread(session_uuid=session_id, title=session_id)
        with session_scope() as session:
            session.add(new_thread)
            session.commit()
            session.refresh(new_thread)
            thread_id = new_thread.thread_id

        _message = {
                "msg":[
                    {
                        "content":"Hello kindly upload an excel or tell me what type of sample dataset you want",
                        "type":"text"
                    }
                ],
                "role":"AI"
            }
        msg_obj = ChatMessage(
            thread_id = thread_id,
            content = dumps(_message),
            role= "system"
        )
        with session_scope() as session:
            session.add(msg_obj)
            session.commit()
        return _message
    except Exception as e:
        logger.exception(f"error in adding session in firestore {e}")


def create_response(last_msg, extra_context):
    """ Creates a Response """
    resp = {
        "msg":[
            {
                "content":"We are encountering an issue at aur end Please try again later",
                "type":"text"

            }
        ],
        "role":"AI"
    }
    try:
        __msg_content = loads(last_msg.content).get("final_answer","Unknown error occured")
        last_msg = resolve_tags(__msg_content)
        pattern = re.compile(r'<(text|chart)>(.*?)</\1>', re.DOTALL)
        msg = []
        for match in pattern.finditer(last_msg):
            tag_type = match.group(1)  # 'text' or 'chart'
            content = match.group(2).strip()
            if tag_type == "chart":
                content = extra_context.get(content,"Unable to dispay chart at the moment")
            msg.append({
                "type": tag_type,
                "content": content
            })

        return {
            "msg": msg,
            "role": "AI"
        }
    except Exception as e:
        logger.exception(f"error in creating response {e}")
    return resp


def check_dataset(session_id):
    """Checks if a dataset is present for that Chat"""
    try:
        check = False
        with session_scope() as session:
            check = session.query(
                ChatThread.dataset_id
            ).filter(
                ChatThread.session_uuid == session_id,
                ChatThread.is_active == True
            ).all()

        logger.info(f"Check dataset --> {check}")

        if check:
            dataset_context = [
                    ("user",(f"I already have a dataset with the name 'Sampel Data'. "
                            "Do not call the 'generate_dataset' tool in your action unless I clearly ask you to do so "
                            "by explicitly stating something like 'create a dataset' or similar instructions.")
                    ),
                    ("assistant", """
                            {
                            "thought": "The user already has a dataset with the given name and does not want me to call the 'generate_dataset' tool unless explicitly instructed. I must check for explicit user intent before proposing dataset creation.",
                            "action": "final_answer",
                            "final_answer": "Understood. I will not call the 'generate_dataset' tool unless you clearly instruct me to create a dataset."
                            }
                            """
                    )
                ]
        else:
            dataset_context = NO_DATASET
    except Exception as e:
        logger.exception(f"error in checking dataset info {e}")
    return dataset_context

async def get_chat_context(key):
    """ Loads the Chat Context """
    prev_context = []
    try:
        _redis_client = get_redis()
        _context =  await _redis_client.get(key)
        if _context:
            logger.info("found previous context on redis")
            prev_context = loads(_context)
            prev_context = messages_from_dict(prev_context)
            logger.info(f"prev context --> {prev_context}")
    except Exception as e:
        logger.info(f"error in getting context {e}")
    return prev_context

def transform_context(context):
    """ Transforms context to dump on Redis """
    try:
        transformed = [msg.dict() for msg in context]
    except Exception as e:
        logger.exception(f"error in transforming context {e}")
        return []
    return transformed

async def set_chat_context(llm_context, extra_context, key):
    """ Sets Context on Redis """
    try:
        _redis = get_redis()
        llm_context = transform_context(llm_context)
        await _redis.set(key, dumps(llm_context))
        logger.info("Sucessfully set context on redis")
    except Exception as e:
        logger.exception(f"error in setting llm context {e}")


@router.get("/create-chat")
async def create_chat(request:Request):
    """ Creates a new Chat """
    try:
        session_id = request.state.session_id
        resp = await asyncio.to_thread(add_chat_thread, session_id)
    except Exception as e:
        logger.exception(f"error in creating chat {e}")
        resp = {"message":"Unable to create a chat at the moment"}
    return resp


@router.post("/get-ai-resp")
async def get_llm_resp(request:Request, background_tasks:BackgroundTasks ,data:QueryPayload):
    resp = {}

    try:
        session_id = request.state.session_id
        user_query = data.user_query
        logger.info(f"uer query --> {user_query}")
        dataset_context = await asyncio.to_thread(check_dataset, session_id)
        logger.info(MASTER_SYSTEM_PROMOPT)
        _context_key = f"{session_id}_main_context"
        prev_context = await get_chat_context(_context_key)
        llm_context = [("system", MASTER_SYSTEM_PROMOPT)] + dataset_context + ONE_SHOT + prev_context + [("user", user_query)]
        initial_state = {"llm_context":llm_context , "extra_context":{}, "session_id":session_id}
        chat_result = await run_graph(initial_state)
        llm_context = chat_result["llm_context"]
        extra_context = chat_result["extra_context"]
        resp = create_response(llm_context[-1], extra_context)
        background_tasks.add_task(set_chat_context, llm_context[1:], extra_context, _context_key)
    except Exception as e:
        logger.exception(f"error in get llm resp {e}")
    return resp