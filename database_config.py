# database_config.py

DATABASES = {
    "default": {
        "driver": "sqlite",
        "database": "app.db",
    },
    "pg_connection": {
        "driver": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "my_postgres_db",
        "user": "postgres",
        "password": "secret_password",
    },
    "mysql_connection": {
        "driver": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "my_mysql_db",
        "user": "root",
        "password": "my_password",
    }
}