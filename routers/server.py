from fastapi import APIRouter, FastAPI, Request, Response, HTTPException, Header, Depends
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
	yield

__prefix__ = "/server"
__tags__ = ["server"]

server_router = APIRouter(
	prefix=__prefix__,
	lifespan=lifespan,
	tags=__tags__
)