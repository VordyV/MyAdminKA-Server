import os
from datetime import datetime
from models import UserModel, UserChronicleModel
from . service_exception import ServiceException
import bcrypt
import secrets

class UserChronicle:

	@staticmethod
	async def register_event(user: int, event_code: str, user_agent: str, user_address: str, details: str = None, user_target: int = None):
		await UserChronicleModel.aio_create(user_initiator=user, event_code=event_code, user_agent=user_agent, user_address=user_address, details=details, user_target=user_target)

class Password:

	@staticmethod
	def encode(value: str) -> str:
		return bcrypt.hashpw(value.encode("utf8"), bcrypt.gensalt())

	@staticmethod
	def verify(password: str, hash: str) -> str:
		return bcrypt.checkpw(password.encode("utf8"), hash.encode("utf8"))

class User:

	@staticmethod
	async def create(name: str, email: str, password: str) -> int:
		if await UserModel.select().where(UserModel.name == name).aio_exists():
			raise ServiceException("Такой логин уже зареган")
		if await UserModel.select().where(UserModel.email == email).aio_exists():
			raise ServiceException("Такой логин уже зареган")

		hashed = Password.encode(password)
		new_user = await UserModel.aio_create(name=name, email=email, hash=hashed)
		return new_user.id

	@staticmethod
	def find(name_or_email: str) -> int:
		result = UserModel.select().where((UserModel.name == name_or_email) | (UserModel.email == name_or_email)).execute()
		for user in result:
			return user.id

	@staticmethod
	async def get_from_uuid(value: str) -> int:
		user = await UserModel.aio_get_or_none(uuid=value)
		return getattr(user, "id")

	@staticmethod
	async def authentication(name_or_email: str, password: str) -> str:
		result = await UserModel.select().where((UserModel.name == name_or_email) | (UserModel.email == name_or_email)).aio_execute()
		for user in result:
			if Password.verify(password, user.hash) and user.is_active:
				#User.add_agent(user.id, agent, address)
				return str(user.uuid)

	@staticmethod
	async def read_info(uid: int):
		user = await UserModel.aio_get(id=uid)
		data = {
			"name": user.name,
			"email": user.email,
			"datetime_create": user.datetime_create,
			"hash_datetime_update": user.hash_datetime_update,

		}
		if user.is_admin: data["is_admin"] = user.is_admin
		return data

	@staticmethod
	async def change_name(uid: int, name: str):
		user = await UserModel.aio_get(id=uid)
		if user.name == name:
			raise ServiceException(f"You can't change your name to the same name")

		if await UserModel.select().where(UserModel.name == name).aio_exists():
			raise ServiceException(f"Try a different name")
		user.name = name
		await user.aio_save()

	@staticmethod
	async def change_email(uid: int, email: str):
		user = await UserModel.aio_get(id=uid)
		if user.email == email:
			raise ServiceException(f"You can't change your e-mail to the same e-mail")

		if await UserModel.select().where(UserModel.email == email).aio_exists():
			raise ServiceException(f"Try a different e-mail")
		user.email = email
		await user.aio_save()

	@staticmethod
	async def change_password(uid: int, password: str, new_password: str):
		user = await UserModel.aio_get(id=uid)

		if not Password.verify(password, user.hash):
			raise ServiceException("Yeah, but the password's wrong")


		if user.hash_datetime_update != user.datetime_create and (datetime.now() - user.hash_datetime_update).total_seconds() < int(os.getenv("TEMP_BAN_CHANGE_PASSWORD_SECONDS")):
			raise ServiceException("Password was recently changed, wait a while to do it again")

		if password == new_password:
			raise ServiceException("You can't change the password to the same password")

		user.hash = Password.encode(new_password)
		user.hash_datetime_update = datetime.now()
		await user.aio_save()

	@staticmethod
	async def delete(uid: int):
		user = await UserModel.aio_get(id=uid)
		await user.aio_delete_instance()