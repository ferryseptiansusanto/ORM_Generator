import os
import sys
import inspect
import sqlite3
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import database_config as project_db_config
from eloquent_base import Model


class TutorialGenerator:
    def __init__(self, models_module, db_path):
        self.models_module = models_module
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.models = self._list_model_classes()

    def _list_model_classes(self):
        classes = []
        for name, obj in inspect.getmembers(self.models_module, inspect.isclass):
            if issubclass(obj, Model) and obj is not Model:
                classes.append(obj)
        return classes

    def _get_model_by_name(self, name):
        for cls in self.models:
            if cls.__name__ == name:
                return cls
        return None

    def _get_table_info(self, table_name):
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        columns = []
        for row in rows:
            columns.append({
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "pk": bool(row[5]),
            })
        return columns

    def _sample_value(self, col_name, col_type, is_update=False):
        """Memberikan nilai dummy yang masuk akal berdasarkan nama kolom."""
        name = col_name.lower()
        if "id" in name and name != "id": return "1"
        if "email" in name: return "'updated@example.com'" if is_update else "'user@example.com'"
        if "password" in name: return "'new_secret'" if is_update else "'secret'"
        if "phone" in name: return "'08999999999'" if is_update else "'08123456789'"
        if "price" in name or "amount" in name or "total" in name: return "250000" if is_update else "150000"
        if "qty" in name or "quantity" in name or "stock" in name: return "50" if is_update else "10"
        if "date" in name: return "'2026-12-31'" if is_update else "'2026-10-23'"
        if "status" in name: return "'inactive'" if is_update else "'active'"
        if "INTEGER" in col_type: return "99" if is_update else "1"
        return f"'{col_name}_updated'" if is_update else f"'{col_name}_value'"

    def _analyze_relations(self, model_cls):
        relations = {'belongs_to': [], 'has_many': [], 'belongs_to_many': []}
        try:
            instance = model_cls()
        except Exception:
            return relations

        custom_methods = [m for m, func in vars(model_cls).items() if not m.startswith('_') and callable(func)]

        for method_name in custom_methods:
            try:
                rel_obj = instance._resolve_relation_object(method_name)
                if not rel_obj: continue

                rel_type = type(rel_obj).__name__
                related_cls_name = rel_obj.related_cls.__name__
                fk = getattr(rel_obj, "foreign_key", None)

                if "BelongsTo" in rel_type and "ToMany" not in rel_type:
                    relations['belongs_to'].append({'name': method_name, 'related': related_cls_name, 'fk': fk})
                elif "BelongsToMany" in rel_type:
                    relations['belongs_to_many'].append({'name': method_name, 'related': related_cls_name})
                elif "HasMany" in rel_type:
                    relations['has_many'].append({'name': method_name, 'related': related_cls_name, 'fk': fk})
            except Exception:
                pass

        return relations

    def _generate_create_fields(self, model_cls, prefix=""):
        table_name = getattr(model_cls, "table", model_cls.__name__.lower() + "s")
        created_col = getattr(model_cls, "created_at_column", "created_at")
        updated_col = getattr(model_cls, "updated_at_column", "updated_at")
        table_info = self._get_table_info(table_name)

        fields = []
        for col in table_info:
            name = col['name']
            if col['pk'] or name in (created_col, updated_col):
                continue
            val = self._sample_value(name, col['type'])
            fields.append(f"{prefix}{name}={val},")
        return fields

    def generate_markdown(self, output_file="ORM_Input_Tutorial.md"):
        md = ["# 📖 Dokumentasi Lengkap CRUD ORM\n"]
        md.append(
            "Gunakan *snippet* kode di bawah ini sebagai referensi cara melakukan **Create, Update, dan Delete** ke masing-masing tabel menggunakan arsitektur `eloquent_base.py`.\n")

        for model_cls in self.models:
            model_name = model_cls.__name__
            table_name = getattr(model_cls, "table", model_name.lower() + "s")
            relations = self._analyze_relations(model_cls)
            table_info = self._get_table_info(table_name)

            created_col = getattr(model_cls, "created_at_column", "created_at")
            updated_col = getattr(model_cls, "updated_at_column", "updated_at")

            md.append(f"## Tabel `{table_name}` (Model: `{model_name}`)")

            # Pengecekan Relasi Master-Detail Sejati
            transaction_detail = None
            for rel in relations['has_many']:
                related_name = rel['related']
                if related_name.endswith("Detail") and related_name.startswith(model_name):
                    transaction_detail = rel
                    break

            # --- Peringatan khusus untuk tabel detail ---
            if model_name.endswith("Detail"):
                md.append(
                    "> ⚠️ **Catatan:** Tabel ini adalah tabel Detail. Untuk integritas data, sangat disarankan melakukan proses Create/Update bersamaan dengan tabel Master-nya menggunakan `DatabaseManager.transaction()`.\n")

            # ---------------------------------------------------------
            # SECTION 1: CREATE
            # ---------------------------------------------------------
            md.append("### 1. Create (Insert Data)")
            md.append("```python")

            if transaction_detail:
                detail_model_name = transaction_detail['related']
                detail_fk = transaction_detail['fk']
                detail_cls = self._get_model_by_name(detail_model_name)

                md.append("from eloquent_base import DatabaseManager\n")
                md.append("# Menggunakan Transaction untuk Master-Detail")
                md.append("with DatabaseManager.transaction():")
                md.append(f"    # 1. Simpan Master ({model_name})")
                md.append(f"    new_master = {model_name}.create(")
                md.extend(self._generate_create_fields(model_cls, prefix="        "))
                md.append("    )\n")

                md.append(f"    # 2. Simpan Detail ({detail_model_name}) menggunakan ID Master")
                md.append(f"    new_detail = {detail_model_name}.create(")
                if detail_cls:
                    detail_fields = self._generate_create_fields(detail_cls, prefix="        ")
                    for df in detail_fields:
                        if df.strip().startswith(f"{detail_fk}="):
                            md.append(f"        {detail_fk}=new_master.id,")
                        else:
                            md.append(df)
                else:
                    md.append(f"        {detail_fk}=new_master.id,")
                    md.append("        # ... isi field lainnya ...")
                md.append("    )")
                md.append("    print('Master dan Detail berhasil disimpan secara transaksional!')")

            else:
                fk_mappings = {}
                if relations['belongs_to']:
                    md.append("# Ambil data parent (Foreign Key) yang dibutuhkan")
                    for rel in relations['belongs_to']:
                        parent = rel['related']
                        fk = rel['fk']
                        var_name = parent.lower()
                        md.append(f"{var_name} = {parent}.query().first()")
                        fk_mappings[fk] = f"{var_name}.id if {var_name} else 1"
                    md.append("")

                md.append(f"new_{model_name.lower()} = {model_name}.create(")
                for col in table_info:
                    name = col['name']
                    if col['pk'] or name in (created_col, updated_col): continue
                    if name in fk_mappings:
                        md.append(f"    {name}={fk_mappings[name]},")
                    else:
                        md.append(f"    {name}={self._sample_value(name, col['type'])},")
                md.append(")")
                md.append(f"print(f'{model_name} berhasil dibuat dengan ID: {{new_{model_name.lower()}.id}}')")

            if relations['belongs_to_many']:
                md.append(f"\n# Hubungkan Relasi Many-to-Many")
                for rel in relations['belongs_to_many']:
                    related = rel['related']
                    rel_name = rel['name']
                    md.append(f"target = {related}.query().first()")
                    md.append(f"if target:")
                    if transaction_detail:
                        md.append(f"    new_master._resolve_relation_object('{rel_name}').attach(target.id)")
                    else:
                        md.append(
                            f"    new_{model_name.lower()}._resolve_relation_object('{rel_name}').attach(target.id)")
                    md.append(f"    print('Relasi ke {related} berhasil di-attach!')")
            md.append("```\n")

            # ---------------------------------------------------------
            # SECTION 2: UPDATE
            # ---------------------------------------------------------
            md.append("### 2. Update Data")
            md.append("```python")
            md.append(f"record = {model_name}.query().first()")
            md.append("if record:")

            update_col = next((c['name'] for c in table_info if
                               not c['pk'] and c['name'] not in (created_col, updated_col) and 'id' not in c['name']),
                              None)
            if not update_col: update_col = table_info[1]['name'] if len(table_info) > 1 else table_info[0]['name']

            col_type = next((c['type'] for c in table_info if c['name'] == update_col), "TEXT")
            new_val = self._sample_value(update_col, col_type, is_update=True)

            if transaction_detail:
                # Transaksional Update untuk Master-Detail
                detail_model_name = transaction_detail['related']
                detail_fk = transaction_detail['fk']

                md.append("    from eloquent_base import DatabaseManager")
                md.append("    ")
                md.append("    # Menggunakan Transaction untuk Update Master sekaligus Menambah/Mengubah Detail")
                md.append("    with DatabaseManager.transaction():")
                md.append("        # 1. Update Field di Tabel Master")
                md.append(f"        record.{update_col} = {new_val}")
                md.append("        record.save()")
                md.append("        ")
                md.append(f"        # 2. Tambahkan Data Detail Baru (contoh)")
                md.append(f"        {detail_model_name}.create(")
                md.append(f"            {detail_fk}=record.id,")
                md.append(f"            # ... isi field detail lainnya ...")
                md.append("        )")
                md.append("        print('Update Master dan penambahan Detail berhasil secara transaksional!')")
            else:
                # Update Standar
                md.append(f"    record.{update_col} = {new_val}")
                md.append("    record.save()")
                md.append("    print('Data berhasil di-update!')")

            md.append("```\n")

            # ---------------------------------------------------------
            # SECTION 3: DELETE
            # ---------------------------------------------------------
            md.append("### 3. Delete Data")
            md.append("```python")
            md.append(f"record = {model_name}.query().first()")
            md.append("if record:")

            if relations['belongs_to_many']:
                md.append(f"    # Bersihkan relasi Many-to-Many di tabel pivot terlebih dahulu")
                for rel in relations['belongs_to_many']:
                    rel_name = rel['name']
                    md.append(
                        f"    record._resolve_relation_object('{rel_name}').detach()  # Menghapus semua relasi pivot")

            md.append("    record.delete()")
            md.append("    print('Data berhasil dihapus dari database!')")
            md.append("```\n")

            md.append("---\n")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md))

        print(f"[SUKSES] Tutorial CRUD Lengkap berhasil di-generate di file: {output_file}")


def main():
    config_dir = Path(os.path.dirname(os.path.abspath(project_db_config.__file__)))
    model_paths = getattr(project_db_config, "MODEL_PATH", {"default": "models"})
    model_dir = model_paths["default"]["path"] if isinstance(model_paths["default"], dict) else model_paths["default"]

    model_path = config_dir / model_dir
    if str(model_path) not in sys.path:
        sys.path.insert(0, str(model_path))
    import models

    from generate_migrate import get_default_database_path
    db_path = get_default_database_path(project_db_config.DATABASES, "")

    generator = TutorialGenerator(models, db_path)
    generator.generate_markdown()


if __name__ == "__main__":
    main()