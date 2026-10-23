import os
import sys
import sqlite3
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Load configuration directly from database_config.py in the same directory.
# The database_config module already reads .env and resolves relative paths
# against the directory where .env is located.
import database_config as project_db_config


def get_default_database_path(databases, config_path):
    if "default" not in databases:
        print("[ERROR] Koneksi 'default' tidak ditemukan di DATABASES.")
        sys.exit(1)

    default_config = databases["default"]
    if not isinstance(default_config, dict):
        print("[ERROR] Konfigurasi 'default' harus berupa dictionary.")
        sys.exit(1)

    db_path = default_config.get("database")
    if not db_path:
        print("[ERROR] Kunci 'database' tidak ditemukan atau kosong pada koneksi 'default'.")
        sys.exit(1)

    # Expand environment variables and user home
    db_path = os.path.expanduser(os.path.expandvars(str(db_path)))

    # database_config.py already resolves relative paths to absolute paths.
    # If for some reason the value is still relative, resolve it against the config file directory.
    db_path_obj = Path(db_path)
    if not db_path_obj.is_absolute():
        config_dir = Path(os.path.dirname(os.path.abspath(config_path)))
        db_path_obj = config_dir / db_path_obj

    return str(db_path_obj)


def get_default_sql_path(sql_paths, config_path):
    if not sql_paths:
        print("[ERROR] SQL_PATH tidak ditemukan di file konfigurasi.")
        sys.exit(1)

    if "default" not in sql_paths:
        print("[ERROR] Koneksi 'default' tidak ditemukan di SQL_PATH.")
        sys.exit(1)

    default_sql = sql_paths["default"]

    # Support both common formats:
    # 1. SQL_PATH = {"default": "/path/to/database.sql"}
    # 2. SQL_PATH = {"default": {"sql": "/path/to/database.sql"}}
    if isinstance(default_sql, dict):
        sql_path = default_sql.get("sql") or default_sql.get("path")
        if not sql_path:
            print("[ERROR] Kunci 'sql' atau 'path' tidak ditemukan pada default SQL_PATH.")
            sys.exit(1)
    else:
        sql_path = default_sql

    sql_path = os.path.expanduser(os.path.expandvars(str(sql_path)))

    sql_path_obj = Path(sql_path)
    if not sql_path_obj.is_absolute():
        config_dir = Path(os.path.dirname(os.path.abspath(config_path)))
        sql_path_obj = config_dir / sql_path_obj

    return str(sql_path_obj)


def run_migration():
    # Gunakan konfigurasi dari database_config.py yang sudah memuat .env.
    # Tidak lagi memerlukan argument path file konfigurasi.
    config_module = project_db_config

    databases = config_module.DATABASES
    sql_paths = getattr(config_module, "SQL_PATH", None)

    config_path = config_module.__file__ or os.path.join(CURRENT_DIR, "database_config.py")

    abs_db_path = get_default_database_path(databases, config_path)
    db_dir = Path(abs_db_path).parent

    db_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Membaca konfigurasi dari: {config_path}")
    print(f"[INFO] Database target: {abs_db_path}")

    abs_sql_path = get_default_sql_path(sql_paths, config_path)

    if not Path(abs_sql_path).is_file():
        print(f"[ERROR] File SQL tidak ditemukan: {abs_sql_path}")
        sys.exit(1)

    if Path(abs_db_path).exists():
        Path(abs_db_path).unlink()
        print(f"[INFO] Database lama '{abs_db_path}' dihapus.")

    print(f"[INFO] Membaca file SQL dari: {abs_sql_path}")
    print(f"[INFO] File database baru akan dibuat di: {abs_db_path}")

    # Gunakan koneksi sqlite3 langsung dengan path absolut.
    connection = sqlite3.connect(abs_db_path)
    try:
        cursor = connection.cursor()

        print("[INFO] Membuat tabel-tabel database...")
        with open(abs_sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        cursor.executescript(sql_script)
        connection.commit()
    finally:
        connection.close()

    # Verify the database file was actually created
    if Path(abs_db_path).is_file():
        print(f"[OK] Migrasi tabel berhasil! Database '{abs_db_path}' siap digunakan.")
    else:
        print(f"[ERROR] Database tidak ditemukan setelah migrasi: {abs_db_path}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
