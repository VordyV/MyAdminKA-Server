#from playhouse.pool import PooledMySQLDatabase
import peewee_async
import inspect

class DataBaseManager:

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