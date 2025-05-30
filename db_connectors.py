#from playhouse.pool import PooledMySQLDatabase
import redis.asyncio as redis
import peewee_async
import inspect

class MySQLManager:

	def __init__(self, name: str, user: str, password: str, address: str, port: int):

		self.__mysql_name = name
		self.__mysql_user = user
		self.__mysql_password = password
		self.__mysql_address = address
		self.__mysql_port = port

		self.__database = peewee_async.PooledMySQLDatabase(


			self.__mysql_name,
			user=self.__mysql_user,
			password=self.__mysql_password,
			host=self.__mysql_address,
			port=self.__mysql_port,
			pool_params={
				"minsize": 2,
				"maxsize": 10,
				"pool_recycle": 2
    		}
		)
		self.__database.set_allow_sync(False)


	def __load_models_from_module(self, module: object):
		members = inspect.getmembers(module, inspect.isclass)
		model_classes = [cls for name, cls in members if name.lower().endswith('model')]
		return model_classes


	async def bind(self, model_module: object):
		models = self.__load_models_from_module(model_module)
		with self.__database.allow_sync():
			self.__database.bind(models)
			self.__database.create_tables(models)

	async def close(self):
		with self.__database.allow_sync():
			self.__database.close()

class RedisManager:

	class RedisClient:

		def __init__(self, pool: redis.ConnectionPool):
			self.__pool = pool
			self.__client: redis.Redis | None = None

		async def __aenter__(self):
			self.bind()
			return self

		def bind(self):
			self.__client = redis.Redis.from_pool(self.__pool)

		async def __aexit__(self, exc_type, exc_val, exc_tb):
			await self.close()

		@property
		def redis(self) -> redis.Redis:
			return self.__client

		async def close(self):
			await self.__client.aclose()

	def __init__(self, address: str, port: int):
		self.__pool = redis.ConnectionPool(
			host=address,
			port=port,
			max_connections=10,
		)

	def client(self) -> RedisClient:
		return self.RedisClient(self.__pool)