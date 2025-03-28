import peewee
import peewee_async
import uuid
import datetime
from slugify import slugify
import shortuuid

def _get_slug(value: str):
	return slugify(value, separator="_")

def _get_shortuuid():
	return shortuuid.ShortUUID().random(length=18)

class UserModel(peewee_async.AioModel):
	name = peewee.CharField(max_length=32, unique=True, index=True)
	email = peewee.CharField(max_length=64, unique=True, index=True)
	uuid = peewee.CharField(max_length=18, index=True, unique=True, default=_get_shortuuid)
	datetime_create = peewee.DateTimeField(default=datetime.datetime.now)
	hash = peewee.CharField(max_length=128)
	hash_datetime_update = peewee.DateTimeField(default=datetime.datetime.now)
	is_admin = peewee.BooleanField(default=False)
	is_active = peewee.BooleanField(default=True)

	class Meta:
		table_name = "myadminka_users"

class ServerModel(peewee_async.AioModel):
	uuid = peewee.CharField(max_length=18, index=True, unique=True, default=_get_shortuuid)
	name = peewee.CharField(max_length=32)
	module = peewee.CharField(max_length=12)
	address = peewee.IPField()
	port = peewee.SmallIntegerField()
	hash = peewee.CharField(max_length=128)
	operator = peewee.ForeignKeyField(UserModel, backref="own_servers")
	datetime_create = peewee.DateTimeField(default=datetime.datetime.now)

	class Meta:
		table_name = "myadminka_servers"

class ServerGroupModel(peewee_async.AioModel):
	server = peewee.ForeignKeyField(ServerModel, backref="server_groups")
	slug = peewee.CharField(max_length=32, index=True)
	name = peewee.CharField(max_length=32)
	datetime_create = peewee.DateTimeField(default=datetime.datetime.now)

	class Meta:
		table_name = "myadminka_server_groups"

class ServerGroupPermissionModel(peewee_async.AioModel):
	group = peewee.ForeignKeyField(ServerGroupModel, index=True)
	value = peewee.CharField(max_length=32)

	class Meta:
		table_name = "myadminka_server_group_perms"

class UserServerGroupModel(peewee_async.AioModel):
	user = peewee.ForeignKeyField(UserModel, index=True)
	group = peewee.ForeignKeyField(ServerGroupModel, index=True)
	datetime_create = peewee.DateTimeField(default=datetime.datetime.now)

	class Meta:
		table_name = "myadminka_users_server_group"

class UserChronicleModel(peewee_async.AioModel):
	user_initiator = peewee.ForeignKeyField(UserModel, index=True)
	datetime_create = peewee.DateTimeField(default=datetime.datetime.now)
	user_target = peewee.ForeignKeyField(UserModel, index=True, null=True)
	event_code = peewee.CharField(max_length=50)
	details = peewee.CharField(null=True)
	user_agent = peewee.CharField()
	user_address = peewee.IPField()

	class Meta:
		table_name = "myadminka_user_chronicles"
