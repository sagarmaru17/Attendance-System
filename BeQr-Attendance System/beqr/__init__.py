try:
	import pymysql
	pymysql.install_as_MySQLdb()
except Exception:
	# If pymysql is not installed yet, the import will fail.
	# Keep the module importable so that users can install the dependency.
	pass

