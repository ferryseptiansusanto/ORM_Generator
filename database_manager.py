# database_manager.py
from contextlib import contextmanager
import os
import sys
import importlib.util

# Name of the environment variable that may point to database_config.py
CONFIG_ENV_VAR = "ORM_DATABASE_CONFIG"

# Default candidate filenames to search relative to a base directory
CONFIG_FILE_CANDIDATES = [
    "database_config.py",
    "config/database_config.py",
    "Config/database_config.py",
]

# Location of this ORM file: normally <main_program>/orm/database_manager.py
LOCAL_ORM_DIR = os.path.dirname(os.path.abspath(__file__))

# Assumed main program folder: the parent of the `orm` directory
PROJECT_ROOT_DIR = os.path.dirname(LOCAL_ORM_DIR)


def _load_config_from_path(path):
    """Dynamically import a database_config.py and return the module."""
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise ImportError(f"File konfigurasi tidak ditemukan: {abs_path}")

    spec = importlib.util.spec_from_file_location("orm_database_config", abs_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Gagal memuat spesifikasi konfigurasi dari: {abs_path}")

    module = importlib.util.module_from_spec(spec)
    # Some config files use __file__ to build paths
    module.__file__ = abs_path

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ImportError(f"Gagal mengeksekusi file konfigurasi {abs_path}: {exc}") from exc

    if not hasattr(module, "DATABASES"):
        raise AttributeError(f"File konfigurasi {abs_path} tidak memiliki variabel DATABASES")

    return module


def _find_config_file():
    """Search for database_config.py in a number of likely base dirs."""
    base_dirs = []
    cwd = os.getcwd()
    if cwd not in base_dirs:
        base_dirs.append(cwd)

    if PROJECT_ROOT_DIR not in base_dirs:
        base_dirs.append(PROJECT_ROOT_DIR)

    # In case the ORM folder itself contains a config file
    if LOCAL_ORM_DIR not in base_dirs:
        base_dirs.append(LOCAL_ORM_DIR)

    for base_dir in base_dirs:
        for candidate in CONFIG_FILE_CANDIDATES:
            candidate_path = os.path.join(base_dir, candidate)
            if os.path.isfile(candidate_path):
                return candidate_path

    return None


def _load_database_config():
    """Locate and load database_config.py from several possible locations."""
    # 1. Environment variable override
    env_path = os.getenv(CONFIG_ENV_VAR)
    if env_path:
        env_path = os.path.expanduser(os.path.expandvars(env_path))
        if os.path.isfile(env_path):
            return _load_config_from_path(env_path)

    # 2. Candidate files relative to cwd, main project folder, and orm folder
    config_path = _find_config_file()
    if config_path is not None:
        return _load_config_from_path(config_path)

    # 3. Fallback to direct import (original behaviour)
    import database_config  # noqa: F401
    return database_config


# Load the configuration once at import time.
# This allows the rest of the ORM to access DATABASES normally.
try:
    config_module = _load_database_config()
    DATABASES = config_module.DATABASES
except Exception as exc:
    raise RuntimeError(
        "Tidak dapat memuat database_config.py. "
        "Atur variabel lingkungan ORM_DATABASE_CONFIG ke path file konfigurasi "
        "atau letakkan database_config.py di direktori kerja saat ini."
    ) from exc


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
