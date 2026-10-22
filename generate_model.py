import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from orm_generator import ORMGenerator


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

    if os.path.isabs(model_path):
        abs_model_path = model_path
    else:
        config_dir = os.path.dirname(os.path.abspath(config_path))
        abs_model_path = os.path.join(config_dir, model_path)

    return abs_model_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_model.py <path_to_database_config.py>")
        sys.exit(1)

    raw_config = sys.argv[1]
    raw_config = os.path.expanduser(os.path.expandvars(raw_config))

    if not os.path.isfile(raw_config):
        print(f"[ERROR] File konfigurasi database tidak ditemukan: {raw_config}")
        sys.exit(1)

    config_module = load_config(raw_config)
    databases = config_module.DATABASES

    abs_db_path = get_default_database_path(databases, raw_config)

    if not os.path.exists(abs_db_path):
        print(f"[ERROR] Database tidak ditemukan: {abs_db_path}")
        print("Jalankan 'python generate_migrate.py <path_to_database_config.py>' terlebih dahulu.")
        sys.exit(1)

    model_paths = getattr(config_module, "MODEL_PATH", None)
    model_dir = get_default_model_path(model_paths, raw_config)

    os.makedirs(model_dir, exist_ok=True)
    output_file = os.path.join(model_dir, "models.py")

    # Dapatkan BASE_DIR dari file konfigurasi.
    base_dir = getattr(config_module, "BASE_DIR", None)
    if not base_dir or not os.path.isdir(base_dir):
        config_dir = os.path.dirname(os.path.abspath(raw_config))
        base_dir = os.path.dirname(config_dir)

    if not os.path.isdir(base_dir):
        print(f"[ERROR] Tidak dapat menentukan BASE_DIR dari konfigurasi.")
        sys.exit(1)

    old_cwd = os.getcwd()

    try:
        # Pindah ke BASE_DIR (root proyek), bukan ke folder database.
        # Dengan begitu DatabaseManager/ORMGenerator dapat menemukan
        # path relatif yang didefinisikan di database_config.py.
        os.chdir(base_dir)
        print(f"[INFO] Mengubah direktori kerja ke: {base_dir}")
        print(f"[INFO] Membaca database dari: {abs_db_path}")
        print(f"[INFO] File model target: {output_file}")
        print("[INFO] Menjalankan ORMGenerator...")

        generator = ORMGenerator(
            connection_name="default",
            output_filename=output_file
        )

        generator.generate(include_pivot_models=False)

        print(f"[OK] File models.py berhasil dibuat di '{output_file}'.")
    finally:
        os.chdir(old_cwd)


if __name__ == "__main__":
    main()
