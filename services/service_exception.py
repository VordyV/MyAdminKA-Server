class ServiceException(Exception):

	def __init__(self, detail: str, code: str = None):
		self.code = code
		self.detail = detail

	def __str__(self) -> str:
		return self.detail

	def __repr__(self) -> str:
		class_name = self.__class__.__name__
		return f"{class_name}(code={self.code!r}, detail={self.detail!r})"