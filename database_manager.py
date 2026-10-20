# database_manager.py
from database_config import DATABASES

class DatabaseManager:
    _connections = {}

    @classmethod
    def get_connection(cls, name: str = "default"):
        if name not in cls._connections:
            config = DATABASES.get(name)
            if not config:
                raise ValueError(f"Konfigurasi database '{name}' tidak ditemukan.")

            driver = config.get("driver")

            if driver == "sqlite":
                import sqlite3
                conn = sqlite3.connect(config["database"])
                conn.row_factory = sqlite3.Row
                cls._connections[name] = conn

            elif driver == "postgresql":
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(
                    host=config.get("host", "localhost"),
                    port=config.get("port", 5432),
                    dbname=config.get("database"),
                    user=config.get("user"),
                    password=config.get("password")
                )
                # Menggunakan RealDictCursor agar hasil query bisa diakses sebagai dictionary seperti SQLite Row
                conn.cursor_factory = psycopg2.extras.RealDictCursor
                cls._connections[name] = conn

            elif driver == "mysql":
                import pymysql
                import pymysql.cursors
                conn = pymysql.connect(
                    host=config.get("host", "localhost"),
                    port=config.get("port", 3306),
                    database=config.get("database"),
                    user=config.get("user"),
                    password=config.get("password"),
                    cursorclass=pymysql.cursors.DictCursor
                )
                cls._connections[name] = conn
            else:
                raise NotImplementedError(f"Driver database '{driver}' belum didukung.")

        return cls._connections[name]

    @classmethod
    def close_all(cls):
        for conn in cls._connections.values():
            conn.close()
        cls._connections.clear()