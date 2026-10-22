# database_config.py

import os

# Ambil path root folder utama (POS_System) dengan naik 1 tingkat dari folder orm
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SQL_PATH = {
    "default": {
        "sql": os.path.join(BASE_DIR, "database", "database.sql")
    }
}

MODEL_PATH = {
    "default": os.path.join(BASE_DIR, "model", "models.py")
}

DATABASES = {
    "default": {
        "driver": "sqlite",
        "database": os.path.join(BASE_DIR, "database", "app.db"),
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
