# database_manager.py
from contextlib import contextmanager
from database_config import DATABASES

class DatabaseManager:
    _connections = {}
    _transaction_depth = {}  # Melacak kedalaman transaksi per koneksi

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

            cls._transaction_depth[name] = 0

        return cls._connections[name]

    @classmethod
    def in_transaction(cls, name: str = "default") -> bool:
        """Mengecek apakah koneksi sedang berada di dalam blok transaksi."""
        return cls._transaction_depth.get(name, 0) > 0

    @classmethod
    def commit_if_auto(cls, name: str = "default") -> None:
        """Hanya melakukan commit otomatis jika TIDAK sedang di dalam blok transaksi."""
        if not cls.in_transaction(name):
            conn = cls.get_connection(name)
            conn.commit()

    @classmethod
    def begin_transaction(cls, name: str = "default") -> None:
        cls.get_connection(name)  # Pastikan koneksi terinisialisasi
        cls._transaction_depth[name] = cls._transaction_depth.get(name, 0) + 1

    @classmethod
    def commit(cls, name: str = "default") -> None:
        depth = cls._transaction_depth.get(name, 0)
        if depth > 0:
            cls._transaction_depth[name] -= 1
            if cls._transaction_depth[name] == 0:
                cls.get_connection(name).commit()
        else:
            cls.get_connection(name).commit()

    @classmethod
    def rollback(cls, name: str = "default") -> None:
        cls._transaction_depth[name] = 0
        cls.get_connection(name).rollback()

    @classmethod
    @contextmanager
    def transaction(cls, name: str = "default"):
        """
        Context manager transaksi bergaya Laravel DB::transaction().
        Otomatis commit jika sukses, dan otomatis rollback jika terjadi exception.
        """
        cls.begin_transaction(name)
        try:
            yield cls.get_connection(name)
            cls.commit(name)
        except Exception as e:
            cls.rollback(name)
            raise e

    @classmethod
    def close_all(cls):
        for conn in cls._connections.values():
            conn.close()
        cls._connections.clear()
        cls._transaction_depth.clear()


# Alias 'DB' ala Facade Laravel (DB.transaction())
DB = DatabaseManager