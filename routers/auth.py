import datetime
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

NameField = Annotated[str, pydantic.Field(min_length=3, max_length=UserModel.name.max_length)]
PasswordField = Annotated[str, pydantic.Field(min_length=7, max_length=UserModel.hash.max_length)]
EmailField = Annotated[str, pydantic.Field(max_length=255)]

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
	name: NameField
	email: EmailField
	password: PasswordField

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
	description="Create a new user. Returns an empty result with code 200",
	response_model=None,
)
async def register(item: RegisterItem, ctx = Depends(auth.uctx)):
	#scheduler = request.app.state.scheduler
	await User.create(name=item.name, email=item.email, password=item.password)
	await delay()
	return Response(status_code=200)

@auth_router.get(
	path="/stress",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))],
	description="stress",
	response_model=dict
)
async def stress(ctx = Depends(auth.ctx)):
	return Response(content="{\"result\": 1}", status_code=200)

class LoginItem(pydantic.BaseModel):
	name: NameField
	password: PasswordField

class LoginResponse(pydantic.BaseModel):
	access_token: str
	refresh_token: str

@auth_router.post(
	path='/login',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_LOGIN_TIMES")), seconds=int(os.getenv("LIMITER_LOGIN_SECONDS"))))],
	description="Authorizes the client by issuing an access token and an refresh",
	response_model=LoginResponse
)
async def login(item: LoginItem, ctx = Depends(auth.uctx)):
	uuid = await User.authentication(item.name, item.password)
	await delay()
	if uuid:
		access_token = auth.security.create_access_token(uuid)
		refresh_token = auth.security.create_refresh_token(uuid)

		payload = auth.security.verify_token(token=authx.RequestToken(
			token=refresh_token,
			location="headers",
			type="refresh"
		))

		async with ctx.redis.client() as client:
			section = f"refreshtoken:{payload.jti}"
			await client.redis.set(section, payload.sub, ex=os.getenv("REFRESH_TOKEN_EXPIRES"))

		return LoginResponse(access_token=access_token, refresh_token=refresh_token)
	raise HTTPException(401, "Bad credentials")

# ================================
# [ /users/me ]

class UserInfoResponse(pydantic.BaseModel):
	name: str
	email: str
	datetime_create: datetime.date | None
	hash_datetime_update: datetime.date | None

def __get_date(value: datetime.datetime | None) -> datetime.date | None:
	try:
		if isinstance(value, datetime.datetime):
			return value.date()
		return None
	except (AttributeError, TypeError):
		return None

@auth_router.get(
	path='/users/me',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))],
	description="Get user information",
	response_model=UserInfoResponse
)
async def user_info(ctx = Depends(auth.ctx)):
	data = await User.read_info(ctx.uid)

	return UserInfoResponse(
		name=data.get("name"),
		email=data.get("email"),
		datetime_create=__get_date(data.get("datetime_create")),
		hash_datetime_update=__get_date(data.get("hash_datetime_update"))
	)

@auth_router.delete(
	path='/users/me',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))],
	description="Deletes the user and their data",
	response_model=None
)
async def user_delete(ctx = Depends(auth.ctx)):
	await User.delete(ctx.uid)
	return Response(status_code=200)
# [ /users/me ]
# ================================

class UserMeChangeNameItem(pydantic.BaseModel):
	name: str = pydantic.Field(min_length=3, max_length=UserModel.name.max_length)

	@pydantic.field_validator('name')
	def validate_name(cls, value: str):
		return _validate_name(value)

@auth_router.post(
	path="/users/me/changename",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))],
	description="Change user name",
	response_model=None
)
async def change_user_name(item: UserMeChangeNameItem, ctx = Depends(auth.ctx)):
	await User.change_name(uid=ctx.uid, name=item.name)
	return Response(status_code=200)

class UserMeChangeEmailItem(pydantic.BaseModel):
	email: EmailField

	@pydantic.field_validator('email')
	def validate_email(cls, value: str):
		return _validate_email(value)

@auth_router.post(
	path="/users/me/changeemail",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_GENERAL_TIMES")), seconds=int(os.getenv("LIMITER_GENERAL_SECONDS"))))],
	description="Change user email",
	response_model=None
)
async def change_user_email(item: UserMeChangeEmailItem, ctx = Depends(auth.ctx)):
	await User.change_email(uid=ctx.uid, email=item.email)
	return Response(status_code=200)

class ChangePasswordItem(pydantic.BaseModel):
	password: PasswordField
	new_password: PasswordField

@auth_router.post(
	path="/users/me/changepassword",
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_CHANGE_PASSWORD_TIMES")), seconds=int(os.getenv("LIMITER_CHANGE_PASSWORD_SECONDS"))))],
	description="Change user password",
	response_model=None
)
async def change_user_password(item: ChangePasswordItem, ctx = Depends(auth.ctx)):
	await User.change_password(uid=ctx.uid, password=item.password, new_password=item.new_password)
	return Response(status_code=200)

class RefreshTokenItem(pydantic.BaseModel):
	refresh_token: str

class RefreshResponse(pydantic.BaseModel):
	access_token: str
	refresh_token: str
	token_type: str

@auth_router.post(
	path='/refresh',
	dependencies=[Depends(RateLimiter(times=int(os.getenv("LIMITER_REFRESH_TIMES")), seconds=int(os.getenv("LIMITER_REFRESH_SECONDS"))))],
	description="Get a new access token",
	response_model=RefreshResponse
)
async def refresh(request: Request, item: RefreshTokenItem):
	try:
		# Verify the refresh token
		refresh_token_payload = auth.security.verify_token(token=authx.RequestToken(
			token=item.refresh_token,
			location="headers",
			type="refresh"
		))

		async with request.app.state.redis.client() as client:

			section = f"refreshtoken:{refresh_token_payload.jti}"

			if not await client.redis.get(section):
				raise Exception("Token has been revoked")

			# Create a new access token
			access_token = auth.security.create_access_token(refresh_token_payload.sub)
			refresh_token = auth.security.create_refresh_token(refresh_token_payload.sub)

			# get payload
			payload = auth.security.verify_token(token=authx.RequestToken(
				token=refresh_token,
				location="headers",
				type="refresh"
			))

			await client.redis.delete(section)

			new_section = f"refreshtoken:{payload.jti}"

			await client.redis.set(new_section, payload.sub, ex=os.getenv("REFRESH_TOKEN_EXPIRES"))

		return RefreshResponse(access_token=access_token, token_type="bearer", refresh_token=refresh_token)
	except Exception as e:
		raise HTTPException(status_code=401, detail=str(e))