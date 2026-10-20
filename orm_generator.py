# orm_generator.py
import os
from typing import List, Dict, Any
from database_manager import DatabaseManager


class ORMGenerator:
    """
    Modul Reverse Engineering untuk membaca skema database secara otomatis
    dan men-generate file class Model Python bergaya Laravel Eloquent.
    """

    def __init__(self, connection_name: str = "default", output_filename: str = "models.py"):
        self.connection_name = connection_name
        self.output_filename = output_filename
        self.conn = DatabaseManager.get_connection(connection_name)

    def _get_tables(self) -> List[str]:
        """Mengambil daftar seluruh tabel di database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        rows = cursor.fetchall()
        return [row["name"] if isinstance(row, dict) else row[0] for row in rows]

    def _get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Membaca struktur kolom dari suatu tabel."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        rows = cursor.fetchall()
        columns = []
        for row in rows:
            col_dict = dict(row) if hasattr(row, "keys") else {
                "cid": row[0], "name": row[1], "type": row[2],
                "notnull": row[3], "dflt_value": row[4], "pk": row[5]
            }
            columns.append(col_dict)
        return columns

    @staticmethod
    def _snake_to_studly(snake_str: str) -> str:
        """Mengubah nama tabel snake_case plural menjadi StudlyCase singular yang akurat."""
        irregular_map = {
            "categories": "Category",
            "companies": "Company",
            "people": "Person",
            "children": "Child"
        }
        if snake_str in irregular_map:
            return irregular_map[snake_str]

        if snake_str.endswith("ies"):
            singular = snake_str[:-3] + "y"
        elif snake_str.endswith("s") and not snake_str.endswith("ss"):
            singular = snake_str[:-1]
        else:
            singular = snake_str

        return "".join(word.capitalize() for word in singular.split("_"))

    def generate(self) -> str:
        """Mengeksekusi proses reverse engineering dan menulis file models.py."""
        tables = self._get_tables()
        model_codes = [
            "# File ini di-generate secara otomatis oleh orm_generator.py",
            "# Jangan diubah secara manual kecuali diperlukan.",
            "from eloquent_base import Model, relation",
            ""
        ]

        table_to_class = {t: self._snake_to_studly(t) for t in tables}

        for table in tables:
            class_name = table_to_class[table]
            columns = self._get_table_columns(table)

            primary_key = "id"
            fillable_cols = []
            has_timestamps = False
            has_soft_deletes = False
            foreign_keys = []

            for col in columns:
                col_name = col["name"]
                is_pk = col["pk"] == 1

                if is_pk:
                    primary_key = col_name

                if col_name in ("created_at", "updated_at"):
                    has_timestamps = True
                elif col_name == "deleted_at":
                    has_soft_deletes = True
                elif not is_pk and col_name not in ("created_at", "updated_at", "deleted_at"):
                    fillable_cols.append(col_name)

                # Deteksi Foreign Key (misal: category_id merujuk ke tabel categories)
                if col_name.endswith("_id") and col_name != primary_key:
                    prefix = col_name[:-3]  # contoh: 'category' dari 'category_id'
                    ref_table = None

                    for t in tables:
                        # Buat bentuk dasar (singular) dari nama tabel untuk dicocokkan dengan prefix
                        singular_t = t
                        if t.endswith("ies"):
                            singular_t = t[:-3] + "y"  # categories -> category
                        elif t.endswith("s") and not t.endswith("ss"):
                            singular_t = t[:-1]  # posts -> post

                        if t == prefix or singular_t == prefix or prefix == singular_t:
                            ref_table = t
                            break

                    if ref_table and ref_table in tables:
                        foreign_keys.append({
                            "col": col_name,
                            "target_table": ref_table,
                            "target_class": table_to_class[ref_table],
                            "relation_name": prefix
                        })

            # Susun kode class Model
            lines = [
                f"class {class_name}(Model):",
                f"    table = \"{table}\"",
                f"    primary_key = \"{primary_key}\"",
                f"    fillable = {fillable_cols!r}"
            ]

            if has_timestamps:
                lines.append("    timestamps = True")
            if has_soft_deletes:
                lines.append("    soft_deletes = True")

            lines.append("")

            # Tambahkan relasi belongs_to
            for fk in foreign_keys:
                lines.extend([
                    "    @relation",
                    f"    def {fk['relation_name']}(self):",
                    f"        return self.belongs_to({fk['target_class']}, foreign_key=\"{fk['col']}\")",
                    ""
                ])

            # Tambahkan relasi has_many secara otomatis
            for other_table in tables:
                if other_table == table:
                    continue
                other_cols = self._get_table_columns(other_table)

                # Sesuaikan pencocokan foreign key ke tabel induk
                singular_table = table[:-1] if table.endswith("s") and not table.endswith("ies") else table
                if table.endswith("ies"):
                    singular_table = table[:-3] + "y"
                expected_fk = f"{singular_table}_id"

                for o_col in other_cols:
                    if o_col["name"] == expected_fk:
                        target_class_name = table_to_class[other_table]
                        rel_method_name = other_table  # misal: products
                        lines.extend([
                            "    @relation",
                            f"    def {rel_method_name}(self):",
                            f"        return self.has_many({target_class_name}, foreign_key=\"{expected_fk}\")",
                            ""
                        ])

            model_codes.append("\n".join(lines))

        full_code = "\n\n".join(model_codes)

        with open(self.output_filename, "w", encoding="utf-8") as f:
            f.write(full_code)

        print(f"[OK] Berhasil men-generate file model ke '{self.output_filename}' dengan relasi otomatis.")
        return full_code