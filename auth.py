from authx import AuthX, AuthXConfig, TokenPayload
from fastapi import Depends, Request, Header
from typing import Annotated
from services.user_service import User
import os
import datetime

config = AuthXConfig()
config.JWT_ALGORITHM = os.getenv("ALGORITHM")
config.JWT_SECRET_KEY =  os.getenv("SECRET_KEY")
config.JWT_ACCESS_TOKEN_EXPIRES = datetime.timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRES")))
config.JWT_REFRESH_TOKEN_EXPIRES = datetime.timedelta(minutes=int(os.getenv("REFRESH_TOKEN_EXPIRES")))

security = AuthX(config=config)

async def get_current_subject(payload: TokenPayload = Depends(security.access_token_required)):
    uid = await User.get_from_uuid(payload.sub)
    return uid

class Ctx:

    def __init__(self, request: Request, user_agent: Annotated[str | None, Header()], uid: int = None):
        self.request = request
        self.user_agent = user_agent
        self.uid = uid

async def ctx(request: Request, user_agent: Annotated[str | None, Header()], uid = Depends(get_current_subject)):
    return Ctx(request, user_agent, uid)

# Unchecked Context
async def uctx(request: Request, user_agent: Annotated[str | None, Header()]):
    return Ctx(request, user_agent)