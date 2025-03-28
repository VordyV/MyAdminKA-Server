import os
import traceback
from typing import Annotated
from fastapi import APIRouter, FastAPI, Request, Response, HTTPException, Header, Depends
from contextlib import asynccontextmanager
from models import UserModel
from services.user_service import User
from fastapi_limiter.depends import RateLimiter
import pydantic
import email_validator
import re
import auth
import asyncio
import random
import authx

@asynccontextmanager
async def lifespan(app: FastAPI):
	yield

__prefix__ = "/auth"
__tags__ = ["auth"]

auth_router = APIRouter(
	prefix=__prefix__,
	lifespan=lifespan,
	tags=__tags__
)

def _validate_name(value: str):
	if not re.match(r"^[a-zA-Z0-9\s]+$", value):
		raise ValueError("Name can only consist of Latin letters and numbers")
	return value

def _validate_email(value: str):
	try:
		emailinfo = email_validator.validate_email(value, check_deliverability=False)
		email = emailinfo.normalized
		return value
	except email_validator.EmailNotValidError as e:
		raise ValueError("Email has an obscure form")

def _validate_password(value: str):
	if not re.match(r'^[A-Za-z\d!@#$%^&*()_+=\-[\]{};:\'"|,.<>/?]+$', value):
		raise ValueError("Password can only consist of Latin characters, numbers and special characters")
	return value


class RegisterItem(pydantic.BaseModel):
	name: str = pydantic.Field(min_length=3, max_length=UserModel.name.max_length)
	email: str
	password: str = pydantic.Field(min_length=7, max_length=UserModel.hash.max_length)

	@pydantic.field_validator('name')
	def validate_name(cls, value: str):
		return _validate_name(value)

	@pydantic.field_validator('email')
	def validate_email(cls, value: str):
		return _validate_email(value)

	@pydantic.field_validator('password')
	def validate_password(cls, value: str):
		return _validate_password(value)

async def delay():
	await asyncio.sleep(round(random.uniform(1.0, 3.0), 4))

@auth_router.post(
	path="/register",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))],
	description="Create a new user. Returns an empty result with code 200"
)
async def register(item: RegisterItem, ctx = Depends(auth.uctx)):
	#scheduler = request.app.state.scheduler
	await User.create(name=item.name, email=item.email, password=item.password)
	await delay()
	return Response(status_code=200)

@auth_router.get(
	path="/stress",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))]
)
async def stress():
	return Response(content="{\"result\": 1}", status_code=200)

class LoginItem(pydantic.BaseModel):
	name: str
	password: str

@auth_router.post(
	path='/login',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_LOGIN_TIMES")), seconds=int(os.getenv("LIMITER_LOGIN_SECONDS"))))]
)
async def login(item: LoginItem, ctx = Depends(auth.uctx)):
	uuid = await User.authentication(item.name, item.password)
	await delay()
	if uuid:
		access_token = auth.security.create_access_token(uuid)
		refresh_token = auth.security.create_refresh_token(uuid)
		return {
			"access_token": access_token,
			"refresh_token": refresh_token
		}
	raise HTTPException(401, "Bad credentials")

# ================================
# [ /users/me ]

@auth_router.get(
	path='/users/me',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))]
)
async def user_info(ctx = Depends(auth.ctx)):
	data = await User.read_info(ctx.uid)
	return data

# [ /users/me ]
# ================================

class UserMeChangeNameItem(pydantic.BaseModel):
	name: str = pydantic.Field(min_length=3, max_length=UserModel.name.max_length)

	@pydantic.field_validator('name')
	def validate_name(cls, value: str):
		return _validate_name(value)

@auth_router.post(
	path="/users/me/changename",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))]
)
async def change_user_name(item: UserMeChangeNameItem, ctx = Depends(auth.ctx)):
	await User.change_name(uid=ctx.uid, name=item.name)
	return Response(status_code=200)

class RefreshTokenItem(pydantic.BaseModel):
	refresh_token: str

@auth_router.post(
	path='/refresh',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_REFRESH_TIMES")), seconds=int(os.getenv("LIMITER_REFRESH_SECONDS"))))]
)
async def refresh(request: Request, item: RefreshTokenItem):
	"""Refresh endpoint that creates a new access token using a refresh token."""
	try:
		# Verify the refresh token
		refresh_token_payload = auth.security.verify_token(token=authx.RequestToken(
			token=item.refresh_token,
			location="headers",
			type="refresh"
		))

		# Create a new access token
		access_token = auth.security.create_access_token(refresh_token_payload.sub)
		return {"access_token": access_token, "token_type": "bearer"}
	except Exception as e:
		raise HTTPException(status_code=401, detail=str(e)) from e