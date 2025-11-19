try:
    import pymysql  # type: ignore

    pymysql.install_as_MySQLdb()
except Exception:
    # PyMySQL optional: only needed when using MySQL backend
    pass
