# database_config.py

import os


def _find_env_file(start_dir: str):
    """Cari file .env mulai dari start_dir, lalu naik ke folder induk hingga ketemu."""
    current = start_dir
    while True:
        candidate = os.path.join(current, ".env")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:  # sudah di root filesystem
            break
        current = parent
    return None


def _load_env_file(env_path: str):
    """Parse file .env sederhana menjadi dictionary."""
    env_vars = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Hapus kutip pembungkus jika ada
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            env_vars[key] = value
    return env_vars


def _get_env(key: str, default=None):
    """Ambil nilai dari env vars yang sudah dimuat (jika ada)."""
    return ENV_VARS.get(key, default)


def _get_env_int(key: str, default: int):
    """Ambil nilai env sebagai integer, fallback ke default jika gagal."""
    try:
        return int(_get_env(key, default))
    except (TypeError, ValueError):
        return default


def _resolve_path(value: str, base_dir: str):
    """Gabungkan path relatif dengan base_dir, atau kembalikan path absolut apa adanya."""
    if not value:
        return None
    if os.path.isabs(value):
        return value
    return os.path.join(base_dir, value)


# BASE_DIR = folder tempat file ini berada
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cari .env mulai dari current working directory (folder tempat script dijalankan),
# lalu fallback ke BASE_DIR jika tidak ketemu.
ENV_VARS = {}
_env_path = _find_env_file(os.getcwd())
if _env_path is None:
    _env_path = _find_env_file(BASE_DIR)

if _env_path is not None:
    ENV_VARS = _load_env_file(_env_path)

# Direktori tempat .env ditemukan.
# Relatif path di .env akan di-resolve terhadap direktori ini,
# bukan terhadap BASE_DIR.
ENV_FILE_DIR = os.path.dirname(_env_path) if _env_path else BASE_DIR

# ---------------------------------------------------------------------------
# SQL_PATH dan MODEL_PATH
# ---------------------------------------------------------------------------
SQL_PATH_DEFAULT = _resolve_path(
    _get_env("SQL_PATH_DEFAULT", "database/database.sql"), ENV_FILE_DIR
)
MODEL_PATH_DEFAULT = _resolve_path(
    _get_env("MODEL_PATH_DEFAULT", "model"), ENV_FILE_DIR
)

SQL_PATH = {
    "default": SQL_PATH_DEFAULT
}

MODEL_PATH = {
    "default": MODEL_PATH_DEFAULT
}

# ---------------------------------------------------------------------------
# DATABASES
# ---------------------------------------------------------------------------
sqlite_db = {
    "driver": _get_env("DATABASE_DEFAULT_DRIVER", "sqlite"),
    "database": _resolve_path(
        _get_env("DATABASE_DEFAULT_DATABASE", "database/app.db"), ENV_FILE_DIR
    ),
}

pg_db = {
    "driver": _get_env("PG_DRIVER", "postgresql"),
    "host": _get_env("PG_HOST", "localhost"),
    "port": _get_env_int("PG_PORT", 5432),
    "database": _get_env("PG_DATABASE", "my_postgres_db"),
    "user": _get_env("PG_USER", "postgres"),
    "password": _get_env("PG_PASSWORD", "secret_password"),
}

mysql_db = {
    "driver": _get_env("MYSQL_DRIVER", "mysql"),
    "host": _get_env("MYSQL_HOST", "localhost"),
    "port": _get_env_int("MYSQL_PORT", 3306),
    "database": _get_env("MYSQL_DATABASE", "my_mysql_db"),
    "user": _get_env("MYSQL_USER", "root"),
    "password": _get_env("MYSQL_PASSWORD", "my_password"),
}

DATABASES = {
    "default": sqlite_db,
    "sqlite": sqlite_db,
    "pg_connection": pg_db,
    "mysql_connection": mysql_db,
}
