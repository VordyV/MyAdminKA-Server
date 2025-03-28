from models import UserModel, ServerModel, ServerGroupModel, UserServerGroupModel, ServerGroupPermissionModel, _get_slug
from peewee import *

class Server:

	operator_label = "OPERATOR"
	max_num_per_user = 10

	@staticmethod
	def create(name: str, module, address: str, port: int, hash: str, uid: int):
		if ServerModel.select().where((ServerModel.operator == uid) & (ServerModel.name == name)).exists(): raise

		if ServerModel.select().where(ServerModel.operator == uid).count() >= Server.max_num_per_user: raise

		user = UserModel.get(id=uid)
		server = ServerModel.create(name=name, module=module, address=address, port=port, hash=hash, operator=user)
		Group.create(name="Administrator", permissions=["*"], sid=server)
		return server.id

	@staticmethod
	def delete(sid: str):
		ServerGroupModel.delete().where(ServerGroupModel.server == sid).execute()
		ServerModel.get(id=sid).delete_instance()

	@staticmethod
	def change(sid: int, name: str = None, address: str = None, port: int = None):
		server = ServerModel.get(id=sid)
		if name:
			if ServerModel.select().where((ServerModel.id == sid) & (ServerModel.name == name)).exists(): raise
			server.name = name
			server.slug = _get_slug(name)
		if address: server.address = address
		if port: server.port = port

		if name or address or port: server.save()

	@staticmethod
	def set_hash(sid: int, new_hash: str):
		server = ServerModel.get(id=sid)
		server.hash = new_hash
		server.save()

	@staticmethod
	def get_all(page: int = 1, paginate_by: int = 20):
		return list(ServerModel.select(ServerModel.id, ServerModel.uuid, ServerModel.name, ServerModel.module, ServerModel.operator, ServerModel.datetime_create).paginate(page=page, paginate_by=paginate_by).dicts())

	@staticmethod
	def get_all_for_user(uid: int):
		owned_servers_query = (
			ServerModel.select(
				ServerModel.id,
				ServerModel.uuid,
				ServerModel.name,
				Value(Server.operator_label).alias("group_name"),
				Value(None).alias("group_slug"),
				Value(None).alias("usg_id"),
			)
			.where(ServerModel.operator == uid)
		)

		group_servers_query = (
			ServerModel.select(
				ServerModel.id,
				ServerModel.uuid,
				ServerModel.name,
				ServerGroupModel.name.alias("group_name"),
				ServerGroupModel.slug.alias("group_slug"),
				UserServerGroupModel.id.alias("usg_id"),
			)
			.join(ServerGroupModel, on=(ServerModel.id == ServerGroupModel.server))
			.join(UserServerGroupModel, on=(ServerGroupModel.id == UserServerGroupModel.group))
			.where(UserServerGroupModel.user == uid)
		)

		all_servers_query = owned_servers_query | group_servers_query

		all_servers_dict = list(all_servers_query.dicts())

		return all_servers_dict

	@staticmethod
	def get_users_for_server(sid: int):
		server = ServerModel.get(id=sid)

		owner_query = (
			UserModel.select(
				UserModel.id,
				UserModel.name,
				Value(Server.operator_label).alias("group_name"),
				Value(None).alias("group_slug"),
				Value(None).alias("usg_id"),
			)
			.where(UserModel.id == server.operator.id)
		)

		group_users_query = (
			UserModel.select(
				UserModel.id,
				UserModel.name,
				ServerGroupModel.name.alias("group_name"),
				ServerGroupModel.slug.alias("group_slug"),
				UserServerGroupModel.id.alias("usg_id"),
			)
			.join(UserServerGroupModel, on=(UserModel.id == UserServerGroupModel.user))
			.join(ServerGroupModel, on=(UserServerGroupModel.group == ServerGroupModel.id))
			.where(ServerGroupModel.server == server)
		)

		all_users_query = owner_query | group_users_query

		all_users_dict = list(all_users_query.dicts())

		return all_users_dict

	@staticmethod
	def get_id_for_uuid(uuid: str, uid: int):
		owner_query = (
			ServerModel
			.select(ServerModel.id)
			.where(
				(ServerModel.uuid == uuid) &
				(ServerModel.operator_id == uid)
			)
		)

		group_query = (
			ServerModel
			.select(ServerModel.id)
			.join(ServerGroupModel, on=(ServerModel.id == ServerGroupModel.server_id))
			.join(UserServerGroupModel, on=(ServerGroupModel.id == UserServerGroupModel.group_id))
			.where(
				(ServerModel.uuid == uuid) &
				(UserServerGroupModel.user_id == uid)
			)
		)

		combined_query = owner_query.union(group_query)

		server = combined_query.first()
		return server.id if server else None

class Group:

	forbidden_groups = ["operator"]

	@staticmethod
	def create(name: str, permissions: list, sid: int):
		if name.lower() in Group.forbidden_groups: raise

		if ServerGroupModel.select().where((ServerGroupModel.server == sid) & (ServerGroupModel.slug == name)).exists(): raise
		group = ServerGroupModel.create(server=sid, name=name, slug=_get_slug(name), permissions=permissions)
		return group.id

	@staticmethod
	def rename(gid: int, new_name: str):
		group = ServerGroupModel.get(id=gid)
		if ServerGroupModel.select().where((ServerGroupModel.server == group.server) & (ServerGroupModel.slug == new_name)).exists(): raise
		group.name = new_name
		group.slug = _get_slug(new_name)
		group.save()

	@staticmethod
	def set_permission(gid: int, value: str):
		value = _get_slug(value)
		if ServerGroupPermissionModel.select().where((ServerGroupPermissionModel.group == gid) & (ServerGroupPermissionModel.value == value)).exists(): raise
		permission = ServerGroupPermissionModel.create(group=gid, value=value)
		return permission.id

	@staticmethod
	def delete_permission(pid: int):
		ServerGroupPermissionModel.get(id=pid).delete_instance()

	@staticmethod
	def delete(gid: int):
		ServerGroupModel.get(id=gid).delete_instance()

	@staticmethod
	def assign(gid: int, uid: int):
		usg = UserServerGroupModel.create(user=uid, group=gid)
		return usg.id

	@staticmethod
	def revoke(usgid: int):
		UserServerGroupModel.get(id=usgid).delete_instance()

	@staticmethod
	def get_all_for_server(sid: int):
		return list(ServerGroupModel.select(ServerGroupModel.id, ServerGroupModel.uuid, ServerGroupModel.slug, ServerGroupModel.name, ServerGroupModel.datetime_create).where(ServerGroupModel.server == sid).dicts())

	@staticmethod
	def get_permissions(gid: int):
		permissions = list(ServerGroupPermissionModel.select(ServerGroupPermissionModel.id, ServerGroupPermissionModel.value).where(ServerGroupPermissionModel.group == gid).dicts())
		return permissions

	@staticmethod
	def has_permission(sid: int, uid: int, permission: str):
		query = (
			ServerModel
			.select()
			.where(
				(ServerModel.id == sid) & (ServerModel.operator == uid)
			)
			.union(
				ServerGroupPermissionModel
				.select()
				.join(ServerGroupModel, on=(ServerGroupPermissionModel.group == ServerGroupModel.id))
				.join(UserServerGroupModel, on=(ServerGroupModel.id == UserServerGroupModel.group))
				.where(
					(UserServerGroupModel.user == uid) &
					(ServerGroupModel.server == sid) &
					(ServerGroupPermissionModel.value == permission)
				)
			)
		)
		return query.exists()

	@staticmethod
	def get_id_for_slug(slug: str, sid: int):
		group = ServerGroupModel.select().where((ServerGroupModel.server == sid) & (ServerGroupModel.slug == slug)).first()
		return group.id if group else None