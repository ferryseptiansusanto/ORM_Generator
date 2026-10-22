import os
import sys
import importlib.util
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


def load_config(config_path):
    if not os.path.isfile(config_path):
        print(f"[ERROR] File konfigurasi database tidak ditemukan: {config_path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("project_db_config", config_path)
    if spec is None or spec.loader is None:
        print(f"[ERROR] Gagal memuat konfigurasi dari: {config_path}")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        print(f"[ERROR] Terjadi kesalahan saat memuat konfigurasi: {exc}")
        sys.exit(1)

    if not hasattr(module, "DATABASES"):
        print(f"[ERROR] File konfigurasi tidak memiliki variabel DATABASES: {config_path}")
        sys.exit(1)

    return module


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

    db_path = os.path.expanduser(os.path.expandvars(str(db_path)))

    if os.path.isabs(db_path):
        abs_db_path = db_path
    else:
        config_dir = os.path.dirname(os.path.abspath(config_path))
        abs_db_path = os.path.join(config_dir, db_path)

    return abs_db_path


def get_default_sql_path(sql_paths, config_path):
    if not sql_paths:
        print("[ERROR] SQL_PATH tidak ditemukan di file konfigurasi.")
        sys.exit(1)

    if "default" not in sql_paths:
        print("[ERROR] Koneksi 'default' tidak ditemukan di SQL_PATH.")
        sys.exit(1)

    default_sql = sql_paths["default"]
    if not isinstance(default_sql, dict):
        print("[ERROR] Konfigurasi 'default' di SQL_PATH harus berupa dictionary.")
        sys.exit(1)

    sql_path = default_sql.get("sql")
    if not sql_path:
        print("[ERROR] Kunci 'sql' tidak ditemukan atau kosong pada koneksi 'default' di SQL_PATH.")
        sys.exit(1)

    sql_path = os.path.expanduser(os.path.expandvars(str(sql_path)))

    if os.path.isabs(sql_path):
        abs_sql_path = sql_path
    else:
        config_dir = os.path.dirname(os.path.abspath(config_path))
        abs_sql_path = os.path.join(config_dir, sql_path)

    return abs_sql_path


def run_migration():
    if len(sys.argv) < 2:
        print("Usage: python generate_migrate.py <path_to_database_config.py>")
        sys.exit(1)

    raw_config = sys.argv[1]
    raw_config = os.path.expanduser(os.path.expandvars(raw_config))

    if not os.path.isfile(raw_config):
        print(f"[ERROR] File konfigurasi database tidak ditemukan: {raw_config}")
        sys.exit(1)

    config_module = load_config(raw_config)

    databases = config_module.DATABASES
    sql_paths = getattr(config_module, "SQL_PATH", None)

    abs_db_path = get_default_database_path(databases, raw_config)
    db_dir = os.path.dirname(abs_db_path)

    os.makedirs(db_dir, exist_ok=True)

    print(f"[INFO] Membaca konfigurasi dari: {raw_config}")
    print(f"[INFO] Database target: {abs_db_path}")

    abs_sql_path = get_default_sql_path(sql_paths, raw_config)

    if not os.path.isfile(abs_sql_path):
        print(f"[ERROR] File SQL tidak ditemukan: {abs_sql_path}")
        sys.exit(1)

    if os.path.exists(abs_db_path):
        os.remove(abs_db_path)
        print(f"[INFO] Database lama '{abs_db_path}' dihapus.")

    print(f"[INFO] Membaca file SQL dari: {abs_sql_path}")
    print(f"[INFO] File database baru akan dibuat di: {abs_db_path}")

    # Gunakan koneksi sqlite3 langsung dengan path absolut.
    # Ini menghindari masalah direktori kerja aktif yang mempengaruhi
    # pembentukan path relatif pada database_manager.
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

    print(f"[OK] Migrasi tabel berhasil! Database '{abs_db_path}' siap digunakan.")


if __name__ == "__main__":
    run_migration()
