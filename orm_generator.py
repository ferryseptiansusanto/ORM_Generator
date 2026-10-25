# File: orm/orm_generator.py
import os
import sys
import inflect
from typing import List, Dict, Any, Optional, Tuple
from database_manager import DatabaseManager

# Initialize the global singular/plural inflect engine instance
p: inflect.engine = inflect.engine()


class ORMGenerator:
    """
    Enterprise Reverse Engineering Engine to inspect database schema definitions
    and automatically compile Laravel Eloquent-style python class structures.
    """

    def __init__(
        self, 
        connection_name: str = "default", 
        output_filename: str = "models.py",
        submodule_name: str = "orm"
    ) -> None:
        """
        Initialize the generator session with target configurations.
        """
        self.connection_name: str = connection_name
        self.output_filename: str = output_filename
        self.submodule_name: str = submodule_name
        self.conn: Any = DatabaseManager.get_connection(connection_name)

    def _get_tables(self) -> List[str]:
        """Fetch a list of all tables registered in the target database."""
        cursor: Any = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        rows: List[Any] = cursor.fetchall()
        return [row["name"] if isinstance(row, dict) else row[0] for row in rows]

    def _get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Extract structured property and constraint properties from columns."""
        cursor: Any = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        rows: List[Any] = cursor.fetchall()
        columns: List[Dict[str, Any]] = []
        for row in rows:
            col_dict: Dict[str, Any] = dict(row) if hasattr(row, "keys") else {
                "cid": row[0], "name": row[1], "type": row[2],
                "notnull": row[3], "dflt_value": row[4], "pk": row[5]
            }
            columns.append(col_dict)
        return columns

    @staticmethod
    def _singularize(word: str) -> str:
        """Transform plural english terms to standard singular versions securely."""
        singular: Any = p.singular_noun(word)
        return singular if singular else word

    @classmethod
    def _snake_to_studly(cls, snake_str: str) -> str:
        """Convert standard snake_case database names to PascalCase class formats."""
        parts: List[str] = snake_str.split("_")
        parts[-1] = cls._singularize(parts[-1])
        return "".join(word.capitalize() for word in parts)

    def _resolve_target_table(self, fk_prefix: str, all_tables: List[str]) -> Optional[str]:
        """Find the original table matched from a standard foreign key context prefix."""
        for t in all_tables:
            singular_t: str = "_".join(t.split("_")[:-1] + [self._singularize(t.split("_")[-1])])
            if t == fk_prefix or singular_t == fk_prefix:
                return t
        return None

    def _detect_pivot_table(
        self, table: str, columns: List[Dict[str, Any]], all_tables: List[str]
    ) -> Optional[Tuple[Dict[str, str], Dict[str, str]]]:
        """
        Evaluate if a structural table acts purely as a Many-to-Many Pivot relationship.
        """
        allowed_extra: set = {"id", "created_at", "updated_at", "deleted_at"}
        fk_cols: List[Dict[str, str]] = []

        for col in columns:
            c_name: str = col["name"]
            if c_name.endswith("_id"):
                prefix: str = c_name[:-3]
                target_t: Optional[str] = self._resolve_target_table(prefix, all_tables)
                if target_t and target_t != table:
                    fk_cols.append({"col": c_name, "prefix": prefix, "target_table": target_t})
            elif c_name not in allowed_extra:
                return None

        if len(fk_cols) != 2:
            return None

        fk1: Dict[str, str] = fk_cols[0]
        fk2: Dict[str, str] = fk_cols[1]
        if fk1["target_table"] == fk2["target_table"]:
            return None

        valid_names: set = {
            f"{fk1['prefix']}_{fk2['prefix']}",
            f"{fk2['prefix']}_{fk1['prefix']}",
            f"{fk1['target_table']}_{fk2['target_table']}",
            f"{fk2['target_table']}_{fk1['target_table']}",
        }

        if table in valid_names or table.startswith("pivot_"):
            return fk1, fk2

        return None

    def generate(self, include_pivot_models: bool = False) -> None:
        """
        Execute full architecture code schema compiling processes into models.py.
        """
        tables: List[str] = self._get_tables()
        table_columns_map: Dict[str, List[Dict[str, Any]]] = {t: self._get_table_columns(t) for t in tables}
        table_to_class: Dict[str, str] = {t: self._snake_to_studly(t) for t in tables}

        pivot_tables: set = set()
        belongs_to_many_map: Dict[str, List[Dict[str, str]]] = {t: [] for t in tables}

        for table in tables:
            cols: List[Dict[str, Any]] = table_columns_map[table]
            pivot_info: Optional[Tuple[Dict[str, str], Dict[str, str]]] = self._detect_pivot_table(table, cols, tables)
            if pivot_info:
                pivot_tables.add(table)
                fk1, fk2 = pivot_info

                belongs_to_many_map[fk1["target_table"]].append({
                    "method_name": fk2["target_table"],
                    "related_class": table_to_class[fk2["target_table"]],
                    "pivot_table": table,
                    "foreign_pivot_key": fk1["col"],
                    "related_pivot_key": fk2["col"],
                })

                belongs_to_many_map[fk2["target_table"]].append({
                    "method_name": fk1["target_table"],
                    "related_class": table_to_class[fk1["target_table"]],
                    "pivot_table": table,
                    "foreign_pivot_key": fk2["col"],
                    "related_pivot_key": fk1["col"],
                })

        # Inject the dynamic submodule folder namespace securely here
        model_codes: List[str] = [
            "# Auto-generated code signature. Do not modify directly.",
            "from typing import Any",  
            f"from {self.submodule_name}.eloquent_base import Model, relation",
            ""
        ]

        for table in tables:
            if table in pivot_tables and not include_pivot_models:
                continue

            class_name: str = table_to_class[table]
            columns: List[Dict[str, Any]] = table_columns_map[table]

            primary_key: str = "id"
            fillable_cols: List[str] = []
            has_timestamps: bool = False
            has_soft_deletes: bool = False

            for col in columns:
                col_name: str = col["name"]
                if col["pk"] == 1:
                    primary_key = col_name
                if col_name in ("created_at", "updated_at"):
                    has_timestamps = True
                elif col_name == "deleted_at":
                    has_soft_deletes = True
                if col_name not in ("id", "created_at", "updated_at", "deleted_at"):
                    fillable_cols.append(col_name)

            model_codes.append(f"@relation")
            model_codes.append(f"class {class_name}(Model):")
            model_codes.append(f"    table: str = \"{table}\"")
            model_codes.append(f"    primary_key: str = \"{primary_key}\"")
            model_codes.append(f"    fillable: list = {fillable_cols}")
            model_codes.append(f"    timestamps: bool = {has_timestamps}")
            model_codes.append(f"    soft_deletes: bool = {has_soft_deletes}")
            model_codes.append("")

            # Compile many-to-many model connections dynamic loops
            if table in belongs_to_many_map:
                for rel in belongs_to_many_map[table]:
                    model_codes.append(f"    def {rel['method_name']}(self) -> Any:")
                    model_codes.append(f"        return self.belongs_to_many(")
                    model_codes.append(f"            \"{rel['related_class']}\",")
                    model_codes.append(f"            table=\"{rel['pivot_table']}\",")
                    model_codes.append(f"            foreign_pivot_key=\"{rel['foreign_pivot_key']}\",")
                    model_codes.append(f"            related_pivot_key=\"{rel['related_pivot_key']}\"")
                    model_codes.append(f"        )")
                    model_codes.append("")

        # Safely execute standard operations to save the files string
        with open(self.output_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(model_codes))
