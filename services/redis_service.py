from db_connectors import RedisManager
from . service_exception import ServiceException

class RedisService:
    redis_manager: RedisManager | None = None

class RefreshToken(RedisService):

    section = "refreshtoken"

    @staticmethod
    async def add(jti: str, sub: str, ttl: int):
        async with RefreshToken.redis_manager.client() as client:
            await client.redis.set(f"{RefreshToken.section}:{jti}", sub, ex=ttl)

    @staticmethod
    async def update(jti: str, new_jit: str, sub: str, ttl: int):
        async with RefreshToken.redis_manager.client() as client:

            if not await client.redis.get(f"{RefreshToken.section}:{jti}"):
                raise ServiceException("Token has been revoked")

            await client.redis.delete(f"{RefreshToken.section}:{jti}")

            await client.redis.set(f"{RefreshToken.section}:{new_jit}", sub, ex=ttl)



