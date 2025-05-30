import traceback
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from routers.auth import auth_router
from db_connectors import MySQLManager, RedisManager
import models
import uvicorn
import os
import signal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import tomllib
from services.service_exception import ServiceException
import auth
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

with open("pyproject.toml", "rb") as f:
	data = tomllib.load(f)
	__version__ = data["tool"]["poetry"]["version"]
	__description__ = data["tool"]["poetry"]["description"]

@asynccontextmanager
async def lifespan(app: FastAPI):
	mysql_name = os.getenv('MYSQL_NAME')
	mysql_user = os.getenv('MYSQL_USER')
	mysql_password = os.getenv('MYSQL_PASSWORD')
	mysql_address = os.getenv('MYSQL_ADDRESS')
	mysql_port = int(os.getenv('MYSQL_PORT'))

	mysql = MySQLManager(
		name=mysql_name,
		user=mysql_user,
		password=mysql_password,
		address=mysql_address,
		port=mysql_port
	)

	redis = RedisManager(
		address=os.getenv("REDIS_ADDRESS"),
		port=int(os.getenv("REDIS_PORT"))
	)

	jobstores = {
		"default": SQLAlchemyJobStore(
			url=f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_address}:{mysql_port}/{mysql_name}")
	}

	try:
		await mysql.bind(models)
		redis_connection = redis.client()
		await FastAPILimiter.init(redis_connection)
		scheduler = AsyncIOScheduler(jobstores=jobstores)
	except Exception as error:
		print(traceback.format_exc())
		print(error)
		print("Server process termination")
		os.kill(os.getpid(), signal.SIGTERM)

	app.state.scheduler = scheduler
	app.state.redis = redis

	yield

	await FastAPILimiter.close()

app = FastAPI(
	title="MyAdminKA API",
	lifespan=lifespan,
	root_path="/api",
	version=__version__,
	description=__description__
)
app.include_router(auth_router)

origins = ["*"]

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

auth.security.handle_errors(app)

@app.exception_handler(ServiceException)
async def http_service_exception_handler(request, exc):
	raise HTTPException(400, exc.detail)

#if __name__ == "__main__":
#	uvicorn.run("main:app", port=int(os.getenv("UVICORN_PORT")), log_level=os.getenv("UVICORN_LOG_LEVEL"))