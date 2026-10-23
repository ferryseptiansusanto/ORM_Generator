import os
import sys
import inspect
import sqlite3
from pathlib import Path
from contextlib import closing

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import database_config as project_db_config
from eloquent_base import DatabaseManager, Model


# =====================================================================
# UTILITIES & CONFIGURATION
# =====================================================================

def get_model_directory(config_module):
    """Mengambil path absolut menuju direktori model dari database_config."""
    model_paths = getattr(config_module, "MODEL_PATH", None)
    if not model_paths:
        return None

    default_model = model_paths.get("default")
    if not default_model:
        return None

    if isinstance(default_model, dict):
        model_dir = default_model.get("path") or default_model.get("model")
    else:
        model_dir = default_model

    if not model_dir:
        return None

    model_dir = os.path.expanduser(os.path.expandvars(str(model_dir)))
    model_path = Path(model_dir)

    if not model_path.is_absolute():
        config_dir = Path(os.path.dirname(os.path.abspath(project_db_config.__file__)))
        model_path = config_dir / model_path

    return str(model_path)


def load_models(model_dir):
    """Mengimpor dan mengembalikan module models."""
    if model_dir not in sys.path:
        sys.path.insert(0, model_dir)
    import models
    return models


def list_model_classes(models_module):
    """Menemukan semua class yang mewarisi eloquent_base.Model."""
    classes = []
    for name, obj in inspect.getmembers(models_module, inspect.isclass):
        if issubclass(obj, Model) and obj is not Model:
            classes.append(obj)
    return classes


def _connect_db(db_path: str) -> sqlite3.Connection:
    """Membuka koneksi sqlite3 baru."""
    return sqlite3.connect(db_path)


def _get_table_info(conn: sqlite3.Connection, table_name: str):
    """Membaca PRAGMA table_info dari SQLite."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    rows = cursor.fetchall()

    columns = []
    for row in rows:
        columns.append({
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        })
    return columns


def _find_pk_column(table_info):
    """Mencari nama kolom Primary Key."""
    for col in table_info:
        if col["pk"]:
            return col["name"]
    return None


def _get_table_name(model_cls):
    """Mendapatkan nama tabel dari model class."""
    try:
        return model_cls.get_table_name()
    except AttributeError:
        return model_cls.__name__.lower() + "s"


# =====================================================================
# DATA GENERATION & TIMESTAMP HANDLING
# =====================================================================

def _sample_value(column_name):
    """Menghasilkan data dummy yang logis berdasarkan nama kolom."""
    name_lower = column_name.lower()
    if "name" in name_lower:
        return "Sample Name"
    if "username" in name_lower:
        return "sampleuser"
    if "email" in name_lower:
        return "sample@example.com"
    if "password" in name_lower:
        return "secretpassword"
    if "title" in name_lower:
        return "Sample Title"
    if "content" in name_lower or "body" in name_lower:
        return "Lorem ipsum dolor sit amet"
    if "phone" in name_lower:
        return "081234567890"
    if "address" in name_lower:
        return "123 Sample Street"
    if "age" in name_lower:
        return 30
    if "is_active" in name_lower or "is_admin" in name_lower or "status" in name_lower:
        return 1
    return f"sample_{name_lower}"


def _get_timestamp_settings(model_cls):
    """Menyimpan konfigurasi timestamp saat ini untuk di-restore nanti."""
    possible_attrs = ["timestamps", "__timestamps__", "created_at_column", "updated_at_column"]
    original = {}
    for attr in possible_attrs:
        if hasattr(model_cls, attr):
            original[attr] = getattr(model_cls, attr)
    return original


def _disable_timestamps(model_cls):
    """Mematikan timestamp sementera jika tabel di DB tidak memiliki kolomnya."""
    if hasattr(model_cls, "timestamps"):
        setattr(model_cls, "timestamps", False)
    if hasattr(model_cls, "__timestamps__"):
        setattr(model_cls, "__timestamps__", False)


def _restore_timestamps(model_cls, original):
    """Mengembalikan konfigurasi timestamp ke semula."""
    for attr, value in original.items():
        setattr(model_cls, attr, value)


def _build_required_data(model_cls, table_info, pk_column_name):
    """
    Menyusun dictionary data otomatis untuk insert, mengabaikan PK dan
    kolom timestamp dinamis berdasarkan properti model.
    """
    created_col = getattr(model_cls, "created_at_column", "created_at")
    updated_col = getattr(model_cls, "updated_at_column", "updated_at")

    data = {}
    for col in table_info:
        if col["pk"] and col["type"].upper() == "INTEGER":
            continue
        if col["name"] in (created_col, updated_col):
            continue
        if col["notnull"] and col["default"] is None:
            data[col["name"]] = _sample_value(col["name"])

    if not data:
        data = {
            col["name"]: _sample_value(col["name"])
            for col in table_info
            if not col["pk"] and col["name"] not in (created_col, updated_col)
        }
    return data


# =====================================================================
# CORE DEMO FUNCTIONS
# =====================================================================

def _fetch_latest_instance(model_cls, db_path, pk_column_name):
    """Mengambil instance model terakhir yang di-insert."""
    if not pk_column_name:
        try:
            return model_cls.query().first()
        except Exception:
            return None
    try:
        return model_cls.query().order_by(pk_column_name, "DESC").first()
    except Exception:
        return None


def safe_create(model_cls, db_path, table_info, pk_column_name):
    """Membuat data baru dengan menangkap silent error."""
    print(f"\n--- CRUD {model_cls.__name__} ---")
    print(" Mencoba create...")

    data = _build_required_data(model_cls, table_info, pk_column_name)
    original_ts = _get_timestamp_settings(model_cls)

    try:
        instance = model_cls(**data)
        if not instance.save():
            print("   [WARNING] Save diam-diam gagal. Mungkin karena 'fillable' atau constraint lain.")
            print("   Mencoba tanpa timestamps...")
            _disable_timestamps(model_cls)
            if not instance.save():
                print("   [ERROR] Save ulang tetap gagal.")
                return None

        print(f"   Create berhasil: {instance}")
        # Re-fetch for full hydration
        instance_with_pk = _fetch_latest_instance(model_cls, db_path, pk_column_name)
        return instance_with_pk if instance_with_pk else instance

    except Exception as exc:
        print(f"   [ERROR SQL] Create gagal karena exception: {exc}")
        return None
    finally:
        _restore_timestamps(model_cls, original_ts)


def demo_query_builder(model_cls):
    """Mendemonstrasikan fitur-fitur QueryBuilder."""
    print(f"\n--- Query Builder {model_cls.__name__} ---")
    try:
        print(f"1. count(): {model_cls.query().count()}")
        first = model_cls.query().first()
        print(f"2. first(): {first}")
        limit_two = model_cls.query().limit(2).get()
        print(f"3. limit(2).get(): {limit_two}")

        pk_name = getattr(model_cls, "primary_key", "id")
        if first:
            pk_value = getattr(first, pk_name, None)
            if pk_value is not None:
                found = model_cls.query().find(pk_value)
                print(f"4. find({pk_value}): {found}")

        try:
            plucked = model_cls.query().pluck(pk_name)
            print(f"5. pluck({pk_name}): {plucked}")
        except Exception as inner_exc:
            print(f"5. pluck() gagal: {inner_exc}")

        ordered = model_cls.query().order_by(pk_name).limit(3).get()
        print(f"6. order_by({pk_name}).limit(3).get(): {ordered}")

    except Exception as exc:
        print(f"Error saat menjalankan demo query builder: {exc}")


def demo_relations(model_cls, instance=None):
    """Scan instance methods that are likely relations."""
    print(f"\n--- Relations {model_cls.__name__} ---")

    custom_methods = [
        m for m, func in vars(model_cls).items()
        if not m.startswith('_') and callable(func)
    ]

    if not custom_methods:
        print("   Model ini tidak memiliki method custom (kemungkinan tidak ada relasi).")
        return

    # Gunakan instance yang dikirim, atau ambil yang ada di DB, atau buat baru
    if instance is None:
        try:
            instance = model_cls.query().first() or model_cls()
        except Exception:
            instance = model_cls()

    print(f"   Scanning {len(custom_methods)} custom method(s)...")
    for method_name in custom_methods:
        try:
            # Gunakan _resolve_relation_object untuk mengekstrak class Relation
            # TANPA men-trigger eksekusi query descriptor
            relation_obj = instance._resolve_relation_object(method_name)

            if relation_obj and hasattr(relation_obj, "get_results"):
                # Barulah kita eksekusi query-nya
                related = relation_obj.get_results()
                print(f"   -> {method_name}() [relasi {type(relation_obj).__name__}]: {related}")
            else:
                print(f"   -> {method_name}() bukan objek relasi yang valid.")
        except Exception as exc:
            print(f"   -> {method_name} gagal: {exc}")

# =====================================================================
# MANY TO MANY & MASTER-DETAIL DEMO
# =====================================================================

def find_master_detail_pair(model_classes):
    """Mencari pasangan model master-detail berdasarkan definisi relasi."""
    for master_cls in model_classes:
        try:
            master_instance = master_cls()
        except Exception:
            continue
        for attr_name in dir(master_instance):
            if attr_name.startswith("_") or attr_name in (
            "has_many", "hasMany", "belongs_to", "belongsTo", "morph_many", "morphMany"):
                continue
            attr = getattr(master_instance, attr_name, None)
            if not callable(attr):
                continue
            try:
                relation = attr()
                related_cls = getattr(relation, "related_cls", None)
                if related_cls and inspect.isclass(related_cls) and related_cls in model_classes:
                    relation_type = type(relation).__name__
                    if "HasMany" in relation_type or "MorphMany" in relation_type:
                        return master_cls, related_cls, relation_type, attr_name
            except Exception:
                continue
    return None, None, None, None


def _extract_foreign_key(master_cls, detail_cls):
    """Mengekstrak nama kolom Foreign Key yang menghubungkan dua model."""
    for cls_a, cls_b in [(master_cls, detail_cls), (detail_cls, master_cls)]:
        try:
            instance = cls_a()
            for attr_name in dir(instance):
                if attr_name.startswith("_") or attr_name in (
                "has_many", "hasMany", "belongs_to", "belongsTo", "morph_many", "morphMany"):
                    continue
                attr = getattr(instance, attr_name, None)
                if callable(attr):
                    relation = attr()
                    if getattr(relation, "related_cls", None) == cls_b:
                        fk = getattr(relation, "foreign_key", None)
                        if fk: return fk
        except Exception:
            pass
    return f"{master_cls.__name__.lower()}_id"


def _create_master_and_detail(master_cls, detail_cls, conn, foreign_key):
    master_info = _get_table_info(conn, _get_table_name(master_cls))
    detail_info = _get_table_info(conn, _get_table_name(detail_cls))
    master_pk = _find_pk_column(master_info)
    detail_pk = _find_pk_column(detail_info)

    original_master = _get_timestamp_settings(master_cls)
    original_detail = _get_timestamp_settings(detail_cls)

    if getattr(master_cls, "created_at_column", "created_at") not in [c["name"] for c in master_info]:
        _disable_timestamps(master_cls)
    if getattr(detail_cls, "created_at_column", "created_at") not in [c["name"] for c in detail_info]:
        _disable_timestamps(detail_cls)

    try:
        master_data = _build_required_data(master_cls, master_info, master_pk)
        master_instance = master_cls(**master_data)
        master_instance.save()
        master_pk_value = getattr(master_instance, master_pk, None) if master_pk else None

        detail_data = _build_required_data(detail_cls, detail_info, detail_pk)
        detail_data[foreign_key] = master_pk_value
        detail_instance = detail_cls(**detail_data)
        detail_instance.save()

        return master_instance, detail_instance
    finally:
        _restore_timestamps(master_cls, original_master)
        _restore_timestamps(detail_cls, original_detail)


def run_master_detail_demo(master_cls, detail_cls, conn, db_path):
    print("\n--- Master-Detail Transaction Demo ---")
    foreign_key = _extract_foreign_key(master_cls, detail_cls)
    print(f"   Foreign key: {foreign_key}")

    try:
        master_count_before = master_cls.query().count()
        detail_count_before = detail_cls.query().count()
    except Exception as exc:
        print(f"   Gagal menghitung data awal: {exc}")
        return

    print("\n1. COMMIT scenario")
    try:
        with DatabaseManager.transaction():
            master, detail = _create_master_and_detail(master_cls, detail_cls, conn, foreign_key)
            print("   Transaction COMMITED secara otomatis.")

        print(f"   Master count: {master_count_before} -> {master_cls.query().count()}")

        # Cleanup
        if master: master.delete()
        if detail: detail.delete()
    except Exception as exc:
        print(f"   COMMIT scenario gagal: {exc}")

    print("\n2. ROLLBACK scenario")
    try:
        with DatabaseManager.transaction():
            master, detail = _create_master_and_detail(master_cls, detail_cls, conn, foreign_key)
            print("   Simulasi kegagalan dengan raise ValueError...")
            raise ValueError("Simulated error inside transaction")
    except ValueError:
        print("   Transaction ROLLED BACK (Sukses ditangkap).")

    master_count_after = master_cls.query().count()
    if master_count_after == master_count_before:
        print("   Rollback verification: data tetap konsisten.")
    else:
        print("   WARNING: jumlah data berubah setelah rollback.")


def cleanup_created(instance, pk_column_name):
    if instance is None: return
    try:
        if getattr(instance, pk_column_name, None) is not None:
            instance.delete()
            print("   Data percobaan berhasil dibersihkan.")
    except Exception as exc:
        print(f"   Cleanup gagal: {exc}")


# =====================================================================
# MAIN RUNNER
# =====================================================================

def main():
    print("=" * 60)
    print("Demo ORM Function – Pengujian seluruh model (Refactored)")
    print("=" * 60)

    model_dir = get_model_directory(project_db_config)
    if not model_dir:
        print("[ERROR] MODEL_PATH tidak ditemukan. Periksa database_config.py.")
        sys.exit(1)

    print(f"[INFO] Load models dari: {model_dir}")
    models_module = load_models(model_dir)
    model_classes = list_model_classes(models_module)

    if not model_classes:
        print("[ERROR] Tidak ada model yang dapat digunakan.")
        sys.exit(1)

    from generate_migrate import get_default_database_path  # type: ignore
    db_path = get_default_database_path(project_db_config.DATABASES, "")
    print(f"[INFO] Database target: {db_path}")

    try:
        conn = _connect_db(db_path)
    except Exception as exc:
        print(f"[ERROR] Gagal membuka database: {exc}")
        sys.exit(1)

    with closing(conn):
        for model_cls in model_classes:
            print("\n" + "=" * 20 + f" MODEL {model_cls.__name__} " + "=" * 20)
            try:
                table_name = _get_table_name(model_cls)
                table_info = _get_table_info(conn, table_name)
                pk_column_name = _find_pk_column(table_info)

                if not table_info:
                    print(f"[WARNING] Tabel '{table_name}' tidak memiliki kolom. Lewati model ini.")
                    continue

                demo_query_builder(model_cls)
                created_instance = safe_create(model_cls, db_path, table_info, pk_column_name)

                if created_instance is not None:
                    print("\n--- Update ---")
                    original = _get_timestamp_settings(model_cls)
                    created_col = getattr(model_cls, "created_at_column", "created_at")
                    updated_col = getattr(model_cls, "updated_at_column", "updated_at")

                    # Pilih kolom yang aman untuk diupdate: bukan PK dan bukan timestamp
                    update_columns = [
                        col["name"] for col in table_info
                        if not col["pk"] and col["name"] not in (created_col, updated_col)
                    ]
                    if not update_columns:
                        print("   Tidak ada kolom non-PK untuk diupdate.")
                    else:
                        update_col = update_columns[0]
                        try:
                            setattr(created_instance, update_col, _sample_value(update_col))
                            _disable_timestamps(model_cls)
                            if created_instance.save():
                                print(f"   Save berhasil. Instance kini: {created_instance}")
                            else:
                                print("   Update gagal secara diam-diam.")
                        except Exception as exc:
                            print(f"   Update gagal Exception: {exc}")
                        finally:
                            _restore_timestamps(model_cls, original)

                    # 1. JALANKAN DEMO RELASI DULU SAAT DATA MASIH ADA DI DB
                    demo_relations(model_cls, created_instance)

                    # 2. BARU BERSIHKAN DATA (CLEANUP)
                    cleanup_created(created_instance, pk_column_name)

                else:
                    # Jika gagal create, tetap jalankan demo relasi dengan instance kosong
                    demo_relations(model_cls)


            except Exception as e:
                print(f"[ERROR] Pengujian model {model_cls.__name__} gagal: {e}")

        # === Tambahan: demo master-detail transaksional (generik) ===
        print("\n" + "=" * 60)
        print("Mencari pasangan master-detail untuk transaction demo...")
        master_cls, detail_cls, relation_type, relation_name = find_master_detail_pair(model_classes)
        if master_cls and detail_cls:
            print(f"   Ditemukan: {master_cls.__name__} -> {detail_cls.__name__} ({relation_type})")
            try:
                run_master_detail_demo(master_cls, detail_cls, conn, db_path)
            except Exception as exc:
                print(f"   Master-detail demo gagal: {exc}")
        else:
            print("   Tidak ditemukan pasangan master-detail yang memenuhi syarat.")

        print("\n" + "=" * 60)
        print("Selesai. Seluruh model telah diuji.")
        print("=" * 60)


if __name__ == "__main__":
    main()