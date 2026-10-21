# orm_generator.py
from typing import List, Dict, Any, Optional, Tuple
from database_manager import DatabaseManager


class ORMGenerator:
    """
    Modul Reverse Engineering Enterprise untuk membaca skema database secara otomatis
    dan men-generate file class Model Python bergaya Laravel Eloquent.
    Mendukung:
    - Konfigurasi Tabel, Primary Key, Fillable, Timestamps, Soft Deletes
    - One-to-Many (has_many & belongs_to)
    - Many-to-Many / Pivot Tables (belongs_to_many)
    - Polymorphic Relations (morph_to & helper morph_many)
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
    def _singularize(word: str) -> str:
        """Mengubah kata plural bahasa Inggris menjadi singular secara akurat."""
        irregular_map = {
            "categories": "category",
            "companies": "company",
            "people": "person",
            "children": "child",
            "men": "man",
            "women": "woman",
        }
        if word in irregular_map:
            return irregular_map[word]
        if word.endswith("ies"):
            return word[:-3] + "y"
        if word.endswith("ses") or word.endswith("xes") or word.endswith("zes"):
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss") and not word.endswith("us"):
            return word[:-1]
        return word

    @classmethod
    def _snake_to_studly(cls, snake_str: str) -> str:
        """Mengubah nama tabel snake_case plural menjadi StudlyCase singular (Nama Class)."""
        parts = snake_str.split("_")
        parts[-1] = cls._singularize(parts[-1])
        return "".join(word.capitalize() for word in parts)

    def _resolve_target_table(self, fk_prefix: str, all_tables: List[str]) -> Optional[str]:
        """Mencari nama tabel asli dari prefix foreign key (contoh: 'category' -> 'categories')."""
        for t in all_tables:
            singular_t = "_".join(t.split("_")[:-1] + [self._singularize(t.split("_")[-1])])
            if t == fk_prefix or singular_t == fk_prefix:
                return t
        return None

    def _detect_pivot_table(
        self, table: str, columns: List[Dict[str, Any]], all_tables: List[str]
    ) -> Optional[Tuple[Dict[str, str], Dict[str, str]]]:
        """
        Mendeteksi apakah suatu tabel merupakan Tabel Pivot (Many-to-Many).
        Kriteria:
        1. Memiliki tepat 2 kolom foreign key (*_id) yang merujuk ke 2 tabel berbeda yang valid.
        2. Kolom lainnya hanya boleh berupa primary key 'id' atau kolom timestamps.
        3. Nama tabel mengandung unsur nama kedua tabel yang dihubungkan (misal: role_user) atau diawali pivot_.
        """
        allowed_extra = {"id", "created_at", "updated_at", "deleted_at"}
        fk_cols = []

        for col in columns:
            c_name = col["name"]
            if c_name.endswith("_id"):
                prefix = c_name[:-3]
                target_t = self._resolve_target_table(prefix, all_tables)
                if target_t and target_t != table:
                    fk_cols.append({"col": c_name, "prefix": prefix, "target_table": target_t})
            elif c_name not in allowed_extra:
                # Memiliki kolom atribut bisnis biasa (misal: 'name', 'price'), bukan tabel pivot murni
                return None

        if len(fk_cols) != 2:
            return None

        fk1, fk2 = fk_cols[0], fk_cols[1]
        if fk1["target_table"] == fk2["target_table"]:
            return None

        # Validasi konvensi penamaan tabel pivot (misal: role_user, user_role, atau users_roles)
        valid_names = {
            f"{fk1['prefix']}_{fk2['prefix']}",
            f"{fk2['prefix']}_{fk1['prefix']}",
            f"{fk1['target_table']}_{fk2['target_table']}",
            f"{fk2['target_table']}_{fk1['target_table']}",
        }

        if table in valid_names or table.startswith("pivot_"):
            return fk1, fk2

        return None

    def generate(self, include_pivot_models: bool = False) -> str:
        """
        Mengeksekusi proses reverse engineering dan menulis file models.py.
        Jika include_pivot_models=False, tabel pivot murni tidak dibuatkan class Model terpisah
        melainkan langsung menjadi relasi @relation belongs_to_many pada kedua tabel induk.
        """
        tables = self._get_tables()
        table_columns_map = {t: self._get_table_columns(t) for t in tables}
        table_to_class = {t: self._snake_to_studly(t) for t in tables}

        # --- PASS 1: Deteksi Tabel Pivot (Many-to-Many) & Relasi Polimorfik ---
        pivot_tables = set()
        # Struktur: { table_name: [ {method_name, related_class, pivot_table, foreign_pivot_key, related_pivot_key} ] }
        belongs_to_many_map: Dict[str, List[Dict[str, str]]] = {t: [] for t in tables}
        # Daftar informasi polimorfik untuk komentar bantuan
        polymorphic_children: List[Dict[str, str]] = []

        for table in tables:
            cols = table_columns_map[table]
            pivot_info = self._detect_pivot_table(table, cols, tables)
            if pivot_info:
                pivot_tables.add(table)
                fk1, fk2 = pivot_info

                # Daftarkan BelongsToMany pada Tabel 1 -> Tabel 2
                belongs_to_many_map[fk1["target_table"]].append({
                    "method_name": fk2["target_table"],  # bentuk plural, misal: roles
                    "related_class": table_to_class[fk2["target_table"]],
                    "pivot_table": table,
                    "foreign_pivot_key": fk1["col"],
                    "related_pivot_key": fk2["col"],
                })

                # Daftarkan BelongsToMany pada Tabel 2 -> Tabel 1
                belongs_to_many_map[fk2["target_table"]].append({
                    "method_name": fk1["target_table"],  # bentuk plural, misal: users
                    "related_class": table_to_class[fk1["target_table"]],
                    "pivot_table": table,
                    "foreign_pivot_key": fk2["col"],
                    "related_pivot_key": fk1["col"],
                })

        # --- PASS 2: Bangun Kode Class untuk Setiap Tabel Model ---
        model_codes = [
            "# File ini di-generate secara otomatis oleh orm_generator.py",
            "# Jangan diubah secara manual kecuali untuk menambahkan Scopes, Accessors, Mutators, atau Observers.",
            "from eloquent_base import Model, relation",
            ""
        ]

        for table in tables:
            if table in pivot_tables and not include_pivot_models:
                continue

            class_name = table_to_class[table]
            columns = table_columns_map[table]
            col_names_set = {c["name"] for c in columns}

            primary_key = "id"
            fillable_cols = []
            has_timestamps = False
            has_soft_deletes = False
            foreign_keys = []
            morph_tos = []

            # Deteksi pasangan kolom Polymorphic (<morph>_id dan <morph>_type)
            morph_columns = set()
            for c_name in col_names_set:
                if c_name.endswith("_type"):
                    morph_prefix = c_name[:-5]  # misal: 'commentable' dari 'commentable_type'
                    id_pair = f"{morph_prefix}_id"
                    if id_pair in col_names_set:
                        morph_tos.append(morph_prefix)
                        morph_columns.add(c_name)
                        morph_columns.add(id_pair)
                        polymorphic_children.append({
                            "child_table": table,
                            "child_class": class_name,
                            "morph_name": morph_prefix
                        })

            for col in columns:
                col_name = col["name"]
                is_pk = col["pk"] == 1

                if is_pk and primary_key == "id":
                    primary_key = col_name

                if col_name in ("created_at", "updated_at"):
                    has_timestamps = True
                elif col_name == "deleted_at":
                    has_soft_deletes = True
                elif not is_pk and col_name not in ("created_at", "updated_at", "deleted_at"):
                    fillable_cols.append(col_name)

                # Deteksi Foreign Key reguler (abaikan jika merupakan bagian dari kolom polymorphic)
                if col_name.endswith("_id") and col_name != primary_key and col_name not in morph_columns:
                    prefix = col_name[:-3]
                    ref_table = self._resolve_target_table(prefix, tables)
                    if ref_table and ref_table in tables:
                        foreign_keys.append({
                            "col": col_name,
                            "target_table": ref_table,
                            "target_class": table_to_class[ref_table],
                            "relation_name": prefix
                        })

            # Susun kerangka atribut class Model
            lines = [
                f"class {class_name}(Model):",
                f"    connection_name = \"{self.connection_name}\"",
                f"    table = \"{table}\"",
                f"    primary_key = \"{primary_key}\"",
                f"    fillable = {fillable_cols!r}"
            ]

            if has_timestamps:
                lines.append("    timestamps = True")
            if has_soft_deletes:
                lines.append("    soft_deletes = True")

            lines.append("")

            # 1. Generate relasi BelongsTo
            for fk in foreign_keys:
                lines.extend([
                    "    @relation",
                    f"    def {fk['relation_name']}(self):",
                    f"        return self.belongs_to({fk['target_class']}, foreign_key=\"{fk['col']}\")",
                    ""
                ])

            # 2. Generate relasi HasMany (dari tabel non-pivot lain yang mengarah ke tabel ini)
            singular_self = "_".join(table.split("_")[:-1] + [self._singularize(table.split("_")[-1])])
            expected_fk = f"{singular_self}_id"

            for other_table in tables:
                if other_table == table or other_table in pivot_tables:
                    continue
                other_cols = table_columns_map[other_table]
                for o_col in other_cols:
                    if o_col["name"] == expected_fk:
                        target_class_name = table_to_class[other_table]
                        lines.extend([
                            "    @relation",
                            f"    def {other_table}(self):",
                            f"        return self.has_many({target_class_name}, foreign_key=\"{expected_fk}\")",
                            ""
                        ])

            # 3. Generate relasi BelongsToMany (Pivot Table)
            for btm in belongs_to_many_map.get(table, []):
                lines.extend([
                    "    @relation",
                    f"    def {btm['method_name']}(self):",
                    f"        return self.belongs_to_many(",
                    f"            {btm['related_class']},",
                    f"            pivot_table=\"{btm['pivot_table']}\",",
                    f"            foreign_pivot_key=\"{btm['foreign_pivot_key']}\",",
                    f"            related_pivot_key=\"{btm['related_pivot_key']}\"",
                    f"        )",
                    ""
                ])

            # 4. Generate relasi Polymorphic MorphTo
            for morph_name in morph_tos:
                lines.extend([
                    "    @relation",
                    f"    def {morph_name}(self):",
                    f"        return self.morph_to(morph_name=\"{morph_name}\")",
                    ""
                ])

            model_codes.append("\n".join(lines).rstrip())

        # Tambahkan petunjuk otomatis jika ada tabel Polimorfik yang terdeteksi
        if polymorphic_children:
            hint_lines = [
                "",
                "# =====================================================================",
                "# PETUNJUK RELASI POLIMORFIK (MORPH_MANY)",
                "# Sistem mendeteksi adanya tabel Polimorfik berikut:",
            ]
            for pm in polymorphic_children:
                hint_lines.extend([
                    f"# - {pm['child_class']} (morph_name='{pm['morph_name']}').",
                    f"#   Tambahkan method berikut pada class Model induk yang memiliki {pm['child_table']}:",
                    f"#   @relation",
                    f"#   def {pm['child_table']}(self):",
                    f"#       return self.morph_many({pm['child_class']}, morph_name=\"{pm['morph_name']}\")"
                ])
            hint_lines.append("# =====================================================================")
            model_codes.append("\n".join(hint_lines))

        full_code = "\n\n\n".join(model_codes) + "\n"

        with open(self.output_filename, "w", encoding="utf-8") as f:
            f.write(full_code)

        print(f"[OK] Berhasil men-generate file model ke '{self.output_filename}' "
              f"(Tabel Model: {len(tables) - len(pivot_tables)}, Tabel Pivot: {len(pivot_tables)}).")
        return full_code