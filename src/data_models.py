from pydantic import BaseModel

class QueryPayload(BaseModel):
    """ User Query Model """
    user_query: str