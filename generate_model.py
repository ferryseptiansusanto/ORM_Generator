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

from orm_generator import ORMGenerator


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


def get_default_model_path(model_paths, config_path):
    if not model_paths:
        print("[ERROR] MODEL_PATH tidak ditemukan di file konfigurasi.")
        sys.exit(1)

    if "default" not in model_paths:
        print("[ERROR] Koneksi 'default' tidak ditemukan di MODEL_PATH.")
        sys.exit(1)

    default_model = model_paths["default"]

    if isinstance(default_model, dict):
        model_path = default_model.get("path") or default_model.get("model")
    elif isinstance(default_model, str):
        model_path = default_model
    else:
        print("[ERROR] Nilai MODEL_PATH['default'] harus berupa string atau dictionary.")
        sys.exit(1)

    if not model_path:
        print("[ERROR] Path model kosong pada MODEL_PATH['default'].")
        sys.exit(1)

    model_path = os.path.expanduser(os.path.expandvars(str(model_path)))

    model_path_obj = Path(model_path)
    if not model_path_obj.is_absolute():
        config_dir = Path(os.path.dirname(os.path.abspath(config_path)))
        model_path_obj = config_dir / model_path_obj

    return str(model_path_obj)


def main():
    # Gunakan konfigurasi dari database_config.py yang sudah memuat .env.
    # Tidak lagi memerlukan argumen path file konfigurasi.
    config_module = project_db_config

    databases = config_module.DATABASES
    model_paths = getattr(config_module, "MODEL_PATH", None)

    config_path = os.path.abspath(
        getattr(config_module, "__file__", os.path.join(CURRENT_DIR, "database_config.py"))
    )

    abs_db_path = get_default_database_path(databases, config_path)

    if not Path(abs_db_path).is_file():
        print(f"[ERROR] Database tidak ditemukan: {abs_db_path}")
        print("Jalankan 'python generate_migrate.py' terlebih dahulu.")
        sys.exit(1)

    model_dir = get_default_model_path(model_paths, config_path)
    os.makedirs(model_dir, exist_ok=True)
    output_file = os.path.join(model_dir, "models.py")

    print(f"[INFO] Membaca konfigurasi dari: {config_path}")
    print(f"[INFO] Database target: {abs_db_path}")
    print(f"[INFO] File model target: {output_file}")
    print("[INFO] Menjalankan ORMGenerator...")

    generator = ORMGenerator(
        connection_name="default",
        output_filename=output_file
    )

    generator.generate(include_pivot_models=False)

    if Path(output_file).is_file():
        print(f"[OK] File models.py berhasil dibuat di '{output_file}'.")
    else:
        print(f"[ERROR] Gagal membuat file model: {output_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
