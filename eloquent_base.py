# eloquent_base.py
import inspect
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from database_manager import DatabaseManager

class MassAssignmentError(Exception):
    """Exception ketika mencoba melakukan mass assignment pada model tanpa konfigurasi fillable yang valid."""
    pass


# =====================================================================
# ARSITEKTUR RELATIONSHIPS & DESCRIPTOR (has_many & belongs_to & BelongsToMany)
# =====================================================================

class Relation:
    def __init__(self, related_cls: Type['Model'], parent: 'Model', foreign_key: str, local_key: str):
        self.related_cls = related_cls
        self.parent = parent
        self.foreign_key = foreign_key
        self.local_key = local_key
        self.query = related_cls.query()
        self._add_constraints()

    def _add_constraints(self) -> None:
        raise NotImplementedError

    def get_results(self) -> Any:
        raise NotImplementedError

    def match_eager(self, models: List['Model'], relation_name: str, nested: List[str] = None) -> None:
        raise NotImplementedError

    def __getattr__(self, name: str):
        if hasattr(self.query, name):
            attr = getattr(self.query, name)
            if callable(attr):
                def wrapper(*args, **kwargs):
                    result = attr(*args, **kwargs)
                    if result is self.query:
                        return self
                    return result
                return wrapper
            return attr
        raise AttributeError(f"Relation '{self.__class__.__name__}' tidak memiliki metode '{name}'.")

class HasMany(Relation):
    def _add_constraints(self) -> None:
        if self.parent._exists:
            local_val = self.parent._attributes.get(self.local_key, getattr(self.parent, self.local_key, None))
            self.query.where(self.foreign_key, local_val)

    def get_results(self) -> List['Model']:
        if not self.parent._exists:
            return []
        return self.query.get()

    def match_eager(self, models: List['Model'], relation_name: str, nested: List[str] = None) -> None:
        keys = list({
            m._attributes.get(self.local_key)
            for m in models
            if m._attributes.get(self.local_key) is not None
        })
        if not keys:
            for m in models:
                m._relations[relation_name] = []
            return

        builder = self.related_cls.query().where_in(self.foreign_key, keys)
        if nested:
            builder.with_relations(*nested)
        related_models = builder.get()

        grouped: Dict[Any, List['Model']] = {k: [] for k in keys}
        for rel_model in related_models:
            fk_val = rel_model._attributes.get(self.foreign_key)
            if fk_val in grouped:
                grouped[fk_val].append(rel_model)

        for m in models:
            lk_val = m._attributes.get(self.local_key)
            m._relations[relation_name] = grouped.get(lk_val, [])


class BelongsTo(Relation):
    def __init__(self, related_cls: Type['Model'], child: 'Model', foreign_key: str, owner_key: str):
        self.owner_key = owner_key
        super().__init__(related_cls, child, foreign_key, owner_key)

    def _add_constraints(self) -> None:
        # Ambil foreign key dengan fallback ke getattr jika tidak ada di _attributes
        fk_val = self.parent._attributes.get(self.foreign_key, getattr(self.parent, self.foreign_key, None))
        if fk_val is not None:
            self.query.where(self.owner_key, fk_val)

    def get_results(self) -> Optional['Model']:
        fk_val = self.parent._attributes.get(self.foreign_key, getattr(self.parent, self.foreign_key, None))
        if fk_val is None:
            return None
        # Pastikan query segar dan constraint diterapkan kembali
        self.query = self.related_cls.query()
        self._add_constraints()
        return self.query.first()

    def match_eager(self, models: List['Model'], relation_name: str, nested: List[str] = None) -> None:
        fk_values = list({
            val for m in models
            for val in [m._attributes.get(self.foreign_key, getattr(m, self.foreign_key, None))]
            if val is not None
        })
        if not fk_values:
            for m in models:
                m._relations[relation_name] = None
            return

        builder = self.related_cls.query().where_in(self.owner_key, fk_values)
        if nested:
            builder.with_relations(*nested)
        related_models = builder.get()

        mapped: Dict[Any, 'Model'] = {
            rel_model._attributes.get(self.owner_key, getattr(rel_model, self.owner_key, None)): rel_model
            for rel_model in related_models
        }

        for m in models:
            fk_val = m._attributes.get(self.foreign_key, getattr(m, self.foreign_key, None))
            m._relations[relation_name] = mapped.get(fk_val, None)


class BelongsToMany(Relation):
    def __init__(
            self,
            related_cls: Type['Model'],
            parent: 'Model',
            pivot_table: str,
            foreign_pivot_key: str,
            related_pivot_key: str,
            parent_key: str,
            related_key: str
    ):
        self.pivot_table = pivot_table
        self.foreign_pivot_key = foreign_pivot_key
        self.related_pivot_key = related_pivot_key
        self.parent_key = parent_key
        self.related_key = related_key
        super().__init__(related_cls, parent, foreign_pivot_key, parent_key)

    @staticmethod
    def _extract_row_val(row: Any, key: str, idx: int = 0) -> Any:
        if isinstance(row, dict):
            return row[key]
        try:
            return row[key]
        except (KeyError, TypeError, IndexError):
            return row[idx]

    def _clear_cache(self) -> None:
        """Membersihkan cache relasi pada parent agar data ditarik ulang dari DB."""
        for rel_name in list(self.parent._relations.keys()):
            rel_instance = self.parent._resolve_relation_object(rel_name)
            # Jika relasi pada key tersebut merujuk ke tabel pivot dan model yang sama, hapus cachenya!
            if isinstance(rel_instance, BelongsToMany) and rel_instance.pivot_table == self.pivot_table:
                del self.parent._relations[rel_name]

    def _add_constraints(self) -> None:
        if self.parent._exists:
            parent_val = self.parent._attributes.get(self.parent_key)
            table = self.related_cls.get_table_name()
            pk = self.related_cls.primary_key
            self.query = self.related_cls.query()
            self.query._selects = [f"{table}.*"]

            conn = DatabaseManager.get_connection(self.parent.connection_name)
            cursor = conn.cursor()
            pivot_sql = f"SELECT {self.related_pivot_key} FROM {self.pivot_table} WHERE {self.foreign_pivot_key} = ?"
            cursor.execute(pivot_sql, (parent_val,))
            related_ids = [
                self._extract_row_val(row, self.related_pivot_key, 0)
                for row in cursor.fetchall()
            ]

            if related_ids:
                self.query.where_in(pk, related_ids)
            else:
                self.query.where(pk, "=", -1)

    def get_results(self) -> 'Collection':
        if not self.parent._exists:
            return Collection([])
        self._add_constraints()
        return self.query.get()

    def match_eager(self, models: List['Model'], relation_name: str, nested: List[str] = None) -> None:
        """Mendukung Eager Loading (.with_('roles')) pada relasi Many-to-Many."""
        parent_keys = list({
            m._attributes.get(self.parent_key)
            for m in models
            if m._attributes.get(self.parent_key) is not None
        })
        if not parent_keys:
            for m in models:
                m._relations[relation_name] = Collection([])
            return

        conn = DatabaseManager.get_connection(self.parent.connection_name)
        cursor = conn.cursor()
        placeholders = ", ".join(["?"] * len(parent_keys))
        pivot_sql = (
            f"SELECT {self.foreign_pivot_key}, {self.related_pivot_key} "
            f"FROM {self.pivot_table} WHERE {self.foreign_pivot_key} IN ({placeholders})"
        )
        cursor.execute(pivot_sql, parent_keys)
        pivot_rows = cursor.fetchall()

        if not pivot_rows:
            for m in models:
                m._relations[relation_name] = Collection([])
            return

        related_ids = list({
            self._extract_row_val(r, self.related_pivot_key, 1)
            for r in pivot_rows
        })

        builder = self.related_cls.query().where_in(self.related_key, related_ids)
        if nested:
            builder.with_relations(*nested)
        related_models = builder.get()

        related_map: Dict[Any, 'Model'] = {
            rm._attributes.get(self.related_key): rm for rm in related_models
        }

        grouped: Dict[Any, List['Model']] = {k: [] for k in parent_keys}
        for r in pivot_rows:
            fk_val = self._extract_row_val(r, self.foreign_pivot_key, 0)
            rk_val = self._extract_row_val(r, self.related_pivot_key, 1)
            if fk_val in grouped and rk_val in related_map:
                grouped[fk_val].append(related_map[rk_val])

        for m in models:
            pk_val = m._attributes.get(self.parent_key)
            m._relations[relation_name] = Collection(grouped.get(pk_val, []))

    def attach(self, id_or_model: Union[int, 'Model', List[Union[int, 'Model']]]) -> None:
        if not self.parent._exists:
            raise ValueError("Tidak dapat melakukan attach pada model yang belum disimpan ke database.")

        items = id_or_model if isinstance(id_or_model, (list, tuple, set)) else [id_or_model]
        parent_val = self.parent._attributes.get(self.parent_key)

        conn = DatabaseManager.get_connection(self.parent.connection_name)
        cursor = conn.cursor()

        for item in items:
            related_id = item._attributes.get(self.related_key, item.id) if isinstance(item, Model) else item
            check_sql = (
                f"SELECT 1 FROM {self.pivot_table} "
                f"WHERE {self.foreign_pivot_key} = ? AND {self.related_pivot_key} = ?"
            )
            cursor.execute(check_sql, (parent_val, related_id))
            if not cursor.fetchone():
                insert_sql = (
                    f"INSERT INTO {self.pivot_table} ({self.foreign_pivot_key}, {self.related_pivot_key}) "
                    f"VALUES (?, ?)"
                )
                cursor.execute(insert_sql, (parent_val, related_id))

        conn.commit()
        self._clear_cache()

    def detach(self, id_or_model: Optional[Union[int, 'Model', List[Union[int, 'Model']]]] = None) -> None:
        if not self.parent._exists:
            return

        parent_val = self.parent._attributes.get(self.parent_key)
        conn = DatabaseManager.get_connection(self.parent.connection_name)
        cursor = conn.cursor()

        if id_or_model is None:
            sql = f"DELETE FROM {self.pivot_table} WHERE {self.foreign_pivot_key} = ?"
            cursor.execute(sql, (parent_val,))
        else:
            items = id_or_model if isinstance(id_or_model, (list, tuple, set)) else [id_or_model]
            for item in items:
                related_id = item._attributes.get(self.related_key, item.id) if isinstance(item, Model) else item
                sql = (
                    f"DELETE FROM {self.pivot_table} "
                    f"WHERE {self.foreign_pivot_key} = ? AND {self.related_pivot_key} = ?"
                )
                cursor.execute(sql, (parent_val, related_id))
        conn.commit()
        self._clear_cache()

    def sync(self, ids: List[Union[int, 'Model']]) -> None:
        target_ids = [
            (item._attributes.get(self.related_key, item.id) if isinstance(item, Model) else item)
            for item in ids
        ]
        current_results = self.get_results()
        current_ids = [item._attributes.get(self.related_key) for item in current_results]

        to_attach = [i for i in target_ids if i not in current_ids]
        to_detach = [i for i in current_ids if i not in target_ids]

        if to_attach:
            self.attach(to_attach)
        if to_detach:
            self.detach(to_detach)

        self._clear_cache()


class MorphMany(Relation):
    def __init__(self, related_cls: Type['Model'], parent: 'Model', morph_name: str):
        self.morph_name = morph_name
        self.foreign_id = f"{morph_name}_id"
        self.foreign_type = f"{morph_name}_type"
        super().__init__(related_cls, parent, self.foreign_id, parent.primary_key)

    def _add_constraints(self) -> None:
        if self.parent._exists:
            local_val = self.parent._attributes.get(self.local_key)
            parent_type = self.parent.__class__.__name__
            self.query.where(self.foreign_id, local_val).where(self.foreign_type, parent_type)

    def get_results(self) -> List['Model']:
        if not self.parent._exists:
            return []
        self._add_constraints()
        return self.query.get()

    def match_eager(self, models: List['Model'], relation_name: str, nested: List[str] = None) -> None:
        # Implementasi sederhana Eager Loading MorphMany
        if not models:
            return

        keys = list(
            {m._attributes.get(self.local_key) for m in models if m._attributes.get(self.local_key) is not None})
        parent_type = models[0].__class__.__name__

        if not keys:
            for m in models:
                m._relations[relation_name] = []
            return

        builder = self.related_cls.query().where_in(self.foreign_id, keys).where(self.foreign_type, parent_type)
        if nested:
            builder.with_relations(*nested)
        related_models = builder.get()

        grouped: Dict[Any, List['Model']] = {k: [] for k in keys}
        for rel_model in related_models:
            fk_val = rel_model._attributes.get(self.foreign_id)
            if fk_val in grouped:
                grouped[fk_val].append(rel_model)

        for m in models:
            lk_val = m._attributes.get(self.local_key)
            m._relations[relation_name] = grouped.get(lk_val, [])


class MorphTo:
    """
    MorphTo tidak mewarisi class Relation karena target modelnya
    berubah-ubah secara dinamis per baris data.
    """

    def __init__(self, child: 'Model', morph_name: str):
        self.child = child
        self.morph_name = morph_name
        self.foreign_id = f"{morph_name}_id"
        self.foreign_type = f"{morph_name}_type"

    def get_results(self) -> Optional['Model']:
        target_type = self.child._attributes.get(self.foreign_type)
        target_id = self.child._attributes.get(self.foreign_id)

        if not target_type or not target_id:
            return None

        # Mencari referensi class secara dinamis dari subclass Model yang terdaftar
        target_cls = next((cls for cls in Model.__subclasses__() if cls.__name__ == target_type), None)

        if not target_cls:
            raise ValueError(f"Target polymorphic class '{target_type}' tidak ditemukan.")

        return target_cls.find(target_id)


# Tambahan class Collection di eloquent_base.py

class Collection(list):
    """
    Pembungkus list kustom bergaya Laravel Collection untuk memanipulasi
    hasil query model di memori secara ekspresif dan Pythonic.
    """
    def __init__(self, iterable=None):
        super().__init__(iterable if iterable is not None else [])

    def where(self, key: str, value: Any) -> 'Collection':
        """Memfilter item di dalam collection berdasarkan nilai atribut."""
        filtered = [
            item for item in self
            if getattr(item, key, None) == value
        ]
        return Collection(filtered)

    def filter(self, callback: Callable[[Any], bool]) -> 'Collection':
        """Memfilter item menggunakan fungsi lambda/callback kustom."""
        filtered = [item for item in self if callback(item)]
        return Collection(filtered)

    def map(self, callback: Callable[[Any], Any]) -> 'Collection':
        """Mentransformasi setiap item di dalam collection."""
        mapped = [callback(item) for item in self]
        return Collection(mapped)

    def group_by(self, key: str) -> Dict[Any, 'Collection']:
        """Mengelompokkan item berdasarkan kunci/atribut tertentu."""
        grouped: Dict[Any, List[Any]] = {}
        for item in self:
            val = getattr(item, key, None)
            if val not in grouped:
                grouped[val] = []
            grouped[val].append(item)
        return {k: Collection(v) for k, v in grouped.items()}

    def groupBy(self, key: str) -> Dict[Any, 'Collection']:
        return self.group_by(key)

    def pluck(self, key: str) -> 'Collection':
        """Mengambil daftar nilai dari satu atribut tertentu saja."""
        plucked = [getattr(item, key, None) for item in self]
        return Collection(plucked)

    def first(self) -> Any:
        """Mengambil item pertama dari collection, atau None jika kosong."""
        return self[0] if self else None

    def last(self) -> Any:
        """Mengambil item terakhir dari collection, atau None jika kosong."""
        return self[-1] if self else None

    def to_dict(self) -> List[dict]:
        """Mengubah seluruh model di dalam collection menjadi list of dictionary."""
        return [item.to_dict() if hasattr(item, "to_dict") else item for item in self]

    def __repr__(self) -> str:
        return f"Collection({super().__repr__()})"


class _RelationList(Collection):
    def __init__(self, iterable, relation_factory: Callable[[], Relation]):
        super().__init__(iterable)
        self._relation_factory = relation_factory

    def __call__(self) -> Relation:
        return self._relation_factory()

    def __getattr__(self, name: str) -> Any:
        rel_obj = self._relation_factory()
        if hasattr(rel_obj, name):
            attr = getattr(rel_obj, name)
            if callable(attr):
                return attr
        raise AttributeError(f"'_RelationList' atau relasi terkait tidak memiliki atribut atau metode '{name}'.")


class relation:
    def __init__(self, func: Callable[['Model'], Relation]):
        self.func = func
        self.name = func.__name__

    def __call__(self, instance: 'Model') -> Relation:
        return self.func(instance)

    def __get__(self, instance: Optional['Model'], owner: Type['Model']) -> Any:
        if instance is None:
            return self

        if self.name not in instance._relations:
            rel_obj = self.func(instance)
            instance._relations[self.name] = rel_obj.get_results()

        cached = instance._relations[self.name]

        if isinstance(cached, list):
            return _RelationList(cached, lambda: self.func(instance))

        if isinstance(cached, Model):
            cached.__dict__["_relation_factory"] = lambda: self.func(instance)

        return cached


# =====================================================================
# QUERY BUILDER
# =====================================================================

class QueryBuilder:
    def __init__(self, model_cls: Type['Model']):
        self.model_cls = model_cls
        self._selects: List[str] = ["*"]
        self._wheres: List[Tuple[str, str, str, Any]] = []
        self._orders: List[str] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._eager_load: List[str] = []
        self._trashed_mode: str = "without"

    def select(self, *columns: str) -> 'QueryBuilder':
        self._selects = list(columns) if columns else ["*"]
        return self

    def where(self, column: str, operator_or_val: Any, value: Any = None) -> 'QueryBuilder':
        if value is None:
            operator = "="
            val = operator_or_val
        else:
            operator = str(operator_or_val).upper()
            val = value

        self._wheres.append(("AND", column, operator, val))
        return self

    def or_where(self, column: str, operator_or_val: Any, value: Any = None) -> 'QueryBuilder':
        if value is None:
            operator = "="
            val = operator_or_val
        else:
            operator = str(operator_or_val).upper()
            val = value

        self._wheres.append(("OR", column, operator, val))
        return self

    def orWhere(self, column: str, operator_or_val: Any, value: Any = None) -> 'QueryBuilder':
        return self.or_where(column, operator_or_val, value)

    def where_null(self, column: str) -> 'QueryBuilder':
        self._wheres.append(("AND", column, "=", None))
        return self

    def where_not_null(self, column: str) -> 'QueryBuilder':
        self._wheres.append(("AND", column, "!=", None))
        return self

    def where_in(self, column: str, values: List[Any]) -> 'QueryBuilder':
        self._wheres.append(("AND", column, "IN", list(values)))
        return self

    def whereIn(self, column: str, values: List[Any]) -> 'QueryBuilder':
        return self.where_in(column, values)

    def with_trashed(self) -> 'QueryBuilder':
        self._trashed_mode = "with"
        return self

    def withTrashed(self) -> 'QueryBuilder':
        return self.with_trashed()

    def only_trashed(self) -> 'QueryBuilder':
        self._trashed_mode = "only"
        return self

    def onlyTrashed(self) -> 'QueryBuilder':
        return self.only_trashed()

    def without_trashed(self) -> 'QueryBuilder':
        self._trashed_mode = "without"
        return self

    def withoutTrashed(self) -> 'QueryBuilder':
        return self.without_trashed()

    def with_relations(self, *relations: str) -> 'QueryBuilder':
        for rel in relations:
            if isinstance(rel, (list, tuple)):
                self._eager_load.extend(rel)
            else:
                self._eager_load.append(rel)
        return self

    def with_(self, *relations: str) -> 'QueryBuilder':
        return self.with_relations(*relations)

    def order_by(self, column: str, direction: str = "ASC") -> 'QueryBuilder':
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError("Direction pada orderBy harus 'ASC' atau 'DESC'.")
        self._orders.append(f"{column} {direction}")
        return self

    def orderBy(self, column: str, direction: str = "ASC") -> 'QueryBuilder':
        return self.order_by(column, direction)

    def limit(self, count: int) -> 'QueryBuilder':
        self._limit = int(count)
        return self

    def take(self, count: int) -> 'QueryBuilder':
        return self.limit(count)

    def offset(self, count: int) -> 'QueryBuilder':
        self._offset = int(count)
        return self

    def skip(self, count: int) -> 'QueryBuilder':
        return self.offset(count)

    def _compile_wheres(self) -> Tuple[str, List[Any]]:
        effective_wheres = list(self._wheres)

        if getattr(self.model_cls, "soft_deletes", False):
            del_col = getattr(self.model_cls, "deleted_at_column", "deleted_at")
            if self._trashed_mode == "without":
                effective_wheres.append(("AND", del_col, "=", None))
            elif self._trashed_mode == "only":
                effective_wheres.append(("AND", del_col, "!=", None))

        if not effective_wheres:
            return "", []

        where_clauses = []
        bindings: List[Any] = []
        for idx, (boolean, col, op, val) in enumerate(effective_wheres):
            prefix = "" if idx == 0 else f"{boolean} "
            if op == "IN":
                if not val:
                    where_clauses.append(f"{prefix}1 = 0")
                else:
                    placeholders = ", ".join(["?"] * len(val))
                    where_clauses.append(f"{prefix}{col} IN ({placeholders})")
                    bindings.extend(val)
            elif val is None:
                if op == "=":
                    where_clauses.append(f"{prefix}{col} IS NULL")
                elif op in ("!=", "<>"):
                    where_clauses.append(f"{prefix}{col} IS NOT NULL")
            else:
                where_clauses.append(f"{prefix}{col} {op} ?")
                bindings.append(val)

        return "WHERE " + " ".join(where_clauses), bindings

    def to_sql(self) -> Tuple[str, List[Any]]:
        table = self.model_cls.get_table_name()
        cols = ", ".join(self._selects)
        sql = [f"SELECT {cols} FROM {table}"]
        bindings: List[Any] = []

        where_sql, where_bindings = self._compile_wheres()
        if where_sql:
            sql.append(where_sql)
            bindings.extend(where_bindings)

        if self._orders:
            sql.append("ORDER BY " + ", ".join(self._orders))

        if self._limit is not None:
            sql.append(f"LIMIT {self._limit}")

        if self._offset is not None:
            sql.append(f"OFFSET {self._offset}")

        return " ".join(sql), bindings

    def _eager_load_relations(self, models: List['Model']) -> None:
        if not models or not self._eager_load:
            return

        grouped_relations: Dict[str, List[str]] = {}
        for rel_path in self._eager_load:
            parts = rel_path.split(".", 1)
            top_rel = parts[0]
            if top_rel not in grouped_relations:
                grouped_relations[top_rel] = []
            if len(parts) > 1:
                grouped_relations[top_rel].append(parts[1])

        sample_instance = self.model_cls()
        for rel_name, nested_list in grouped_relations.items():
            rel_obj = sample_instance._resolve_relation_object(rel_name)
            if rel_obj is None:
                raise AttributeError(
                    f"Model '{self.model_cls.__name__}' tidak memiliki definisi relasi '{rel_name}'."
                )
            rel_obj.match_eager(models, rel_name, nested=nested_list)

    def get(self) -> Collection:
        sql, bindings = self.to_sql()
        conn = DatabaseManager.get_connection(self.model_cls.connection_name)
        cursor = conn.cursor()
        cursor.execute(sql, bindings)
        rows = cursor.fetchall()

        models = [self.model_cls._hydrate(dict(row)) for row in rows]

        if self._eager_load and models:
            self._eager_load_relations(models)

        # Bungkus hasil list model ke dalam Collection berfitur tinggi
        return Collection(models)

    def pluck(self, column: str) -> Collection:
        """Mengambil Collection berisi nilai dari satu kolom langsung via QueryBuilder."""
        return self.get().pluck(column)

    def first(self) -> Optional['Model']:
        self.limit(1)
        results = self.get()
        return results[0] if results else None

    def find(self, pk_value: Any) -> Optional['Model']:
        return self.where(self.model_cls.primary_key, pk_value).first()

    def count(self) -> int:
        prev_selects = self._selects
        self._selects = ["COUNT(*) as aggregate_count"]
        sql, bindings = self.to_sql()
        self._selects = prev_selects

        conn = DatabaseManager.get_connection(self.model_cls.connection_name)
        cursor = conn.cursor()
        cursor.execute(sql, bindings)
        row = cursor.fetchone()
        return row["aggregate_count"] if row else 0

    def update(self, **kwargs) -> int:
        filtered_data = self.model_cls._filter_fillable(kwargs)
        if not filtered_data:
            return 0

        temp_instance = self.model_cls()
        mutated_data = {}
        for k, v in filtered_data.items():
            temp_instance._set_attribute_via_mutator(k, v)
            if k in temp_instance._attributes:
                mutated_data[k] = temp_instance._attributes[k]

        if getattr(self.model_cls, "timestamps", False):
            upd_col = getattr(self.model_cls, "updated_at_column", "updated_at")
            if upd_col and upd_col not in mutated_data:
                mutated_data[upd_col] = self.model_cls._fresh_timestamp()

        table = self.model_cls.get_table_name()
        set_clause = ", ".join([f"{col} = ?" for col in mutated_data.keys()])
        bindings = list(mutated_data.values())

        where_sql, where_bindings = self._compile_wheres()
        sql = f"UPDATE {table} SET {set_clause}"
        if where_sql:
            sql += f" {where_sql}"
            bindings.extend(where_bindings)

        conn = DatabaseManager.get_connection(self.model_cls.connection_name)
        cursor = conn.cursor()
        cursor.execute(sql, bindings)
        conn.commit()
        return cursor.rowcount

    def delete(self) -> int:
        table = self.model_cls.get_table_name()
        where_sql, where_bindings = self._compile_wheres()
        conn = DatabaseManager.get_connection(self.model_cls.connection_name)
        cursor = conn.cursor()

        if getattr(self.model_cls, "soft_deletes", False):
            del_col = getattr(self.model_cls, "deleted_at_column", "deleted_at")
            now_str = self.model_cls._fresh_timestamp()
            set_cols = [f"{del_col} = ?"]
            bindings = [now_str]

            if getattr(self.model_cls, "timestamps", False):
                upd_col = getattr(self.model_cls, "updated_at_column", "updated_at")
                if upd_col:
                    set_cols.append(f"{upd_col} = ?")
                    bindings.append(now_str)

            sql = f"UPDATE {table} SET {', '.join(set_cols)}"
            if where_sql:
                sql += f" {where_sql}"
                bindings.extend(where_bindings)
            cursor.execute(sql, bindings)
        else:
            sql = f"DELETE FROM {table}"
            if where_sql:
                sql += f" {where_sql}"
            cursor.execute(sql, where_bindings)

        conn.commit()
        return cursor.rowcount

    def force_delete(self) -> int:
        prev_mode = self._trashed_mode
        self._trashed_mode = "with"
        table = self.model_cls.get_table_name()
        where_sql, where_bindings = self._compile_wheres()
        self._trashed_mode = prev_mode

        sql = f"DELETE FROM {table}"
        if where_sql:
            sql += f" {where_sql}"

        conn = DatabaseManager.get_connection(self.model_cls.connection_name)
        cursor = conn.cursor()
        cursor.execute(sql, where_bindings)
        conn.commit()
        return cursor.rowcount

    def forceDelete(self) -> int:
        return self.force_delete()

    def restore(self) -> int:
        if not getattr(self.model_cls, "soft_deletes", False):
            return 0

        prev_mode = self._trashed_mode
        if self._trashed_mode == "without":
            self._trashed_mode = "only"

        table = self.model_cls.get_table_name()
        del_col = getattr(self.model_cls, "deleted_at_column", "deleted_at")
        where_sql, where_bindings = self._compile_wheres()
        self._trashed_mode = prev_mode

        set_cols = [f"{del_col} = NULL"]
        bindings: List[Any] = []

        if getattr(self.model_cls, "timestamps", False):
            upd_col = getattr(self.model_cls, "updated_at_column", "updated_at")
            if upd_col:
                set_cols.append(f"{upd_col} = ?")
                bindings.append(self.model_cls._fresh_timestamp())

        sql = f"UPDATE {table} SET {', '.join(set_cols)}"
        if where_sql:
            sql += f" {where_sql}"
            bindings.extend(where_bindings)

        conn = DatabaseManager.get_connection(self.model_cls.connection_name)
        cursor = conn.cursor()
        cursor.execute(sql, bindings)
        conn.commit()
        return cursor.rowcount

    def paginate(self, per_page: int = 15, page: int = 1) -> Dict[str, Any]:
        """
        Membagi hasil query menjadi halaman-halaman (pagination).
        Mengembalikan dictionary berisi data list/collection dan metadata halaman.
        """
        # 1. Hitung total data keseluruhan (tanpa limit/offset)
        total = self.count()

        # 2. Hitung total halaman
        import math
        last_page = math.ceil(total / per_page) if total > 0 else 1

        # Validasi agar page tidak keluar batas
        page = max(1, min(page, last_page))
        offset_val = (page - 1) * per_page

        # 3. Terapkan limit dan offset, lalu ambil data
        self.limit(per_page).offset(offset_val)
        items = self.get()

        # 4. Kembalikan struktur data ala Laravel LengthAwarePaginator
        return {
            "data": items,
            "current_page": page,
            "per_page": per_page,
            "total": total,
            "last_page": last_page,
            "from": offset_val + 1 if total > 0 else 0,
            "to": min(offset_val + per_page, total)
        }

    def search(self, column: str, keyword: str) -> 'QueryBuilder':
        """Helper untuk pencarian parsial (LIKE %keyword%)."""
        if keyword:
            return self.where(column, "LIKE", f"%{keyword}%")
        return self

    def where_date_between(self, column: str, start_date: str, end_date: str) -> 'QueryBuilder':
        """Helper untuk memfilter rentang tanggal."""
        if start_date and end_date:
            return self.where(column, ">=", start_date).where(column, "<=", end_date)
        return self

    def __getattr__(self, name: str) -> Callable:
        scope_callable = self.model_cls._resolve_scope(name)
        if scope_callable is not None:
            def scope_wrapper(*args, **kwargs) -> 'QueryBuilder':
                result = scope_callable(self, *args, **kwargs)
                return result if isinstance(result, QueryBuilder) else self
            return scope_wrapper

        raise AttributeError(
            f"'QueryBuilder' maupun Model '{self.model_cls.__name__}' tidak memiliki metode atau scope '{name}'."
        )


# =====================================================================
# METACLASS & BASE MODEL
# =====================================================================

class ModelMeta(type):
    def __getattr__(cls, name: str):
        # Hindari pencegatan pada atribut internal Python / dunder
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(f"Model '{cls.__name__}' tidak memiliki atribut '{name}'.")

        builder = cls.query()
        if hasattr(builder, name):
            return getattr(builder, name)
        raise AttributeError(f"Model '{cls.__name__}' tidak memiliki atribut, metode, atau scope '{name}'.")

class Model(metaclass=ModelMeta):
    connection_name: str = "default"
    table: Optional[str] = None
    primary_key: str = "id"

    fillable: List[str] = []
    guarded: List[str] = ["*"]
    appends: List[str] = []

    soft_deletes: bool = False
    deleted_at_column: str = "deleted_at"

    timestamps: bool = False
    created_at_column: str = "created_at"
    updated_at_column: str = "updated_at"
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"

    #Registri global untuk mencatat Observer
    _observers_registry: Dict[str, List[Any]] = {}

    _RESERVED_CLASS_ATTRS = {
        "connection_name", "table", "primary_key", "fillable", "guarded", "appends",
        "soft_deletes", "deleted_at_column", "timestamps",
        "created_at_column", "updated_at_column", "timestamp_format"
    }

    def __init__(self, **kwargs):
        self.__dict__["_attributes"] = {}
        self.__dict__["_original"] = {}
        self.__dict__["_relations"] = {}
        self.__dict__["_exists"] = False
        self.__dict__["_relation_factory"] = None
        self.__dict__["_in_mutator"] = set()

        if kwargs:
            self.fill(**kwargs)

    def __call__(self) -> Relation:
        factory = self.__dict__.get("_relation_factory")
        if callable(factory):
            return factory()
        raise TypeError(f"Instance '{self.__class__.__name__}' tidak sedang bertindak sebagai relasi yang callable.")

    @classmethod
    def get_table_name(cls) -> str:
        if cls.table:
            return cls.table
        return f"{cls.__name__.lower()}s"

    @classmethod
    def from_connection(cls, name: str) -> Type['Model']:
        return type(
            f"{cls.__name__}_{name}",
            (cls,),
            {
                "connection_name": name,
                "table": cls.get_table_name(),
                "primary_key": cls.primary_key,
                "fillable": list(cls.fillable),
                "guarded": list(cls.guarded),
                "appends": list(cls.appends),
                "soft_deletes": cls.soft_deletes,
                "deleted_at_column": cls.deleted_at_column,
                "timestamps": cls.timestamps,
                "created_at_column": cls.created_at_column,
                "updated_at_column": cls.updated_at_column,
                "timestamp_format": cls.timestamp_format,
            }
        )

    @classmethod
    def query(cls) -> QueryBuilder:
        return QueryBuilder(cls)

    @classmethod
    def all(cls) -> List['Model']:
        return cls.query().get()

    @staticmethod
    def _studly_case(snake_str: str) -> str:
        return "".join(word.capitalize() for word in snake_str.split("_"))

    @classmethod
    def _resolve_scope(cls, name: str) -> Optional[Callable]:
        snake_scope = f"scope_{name}"
        camel_scope = f"scope{cls._studly_case(name)}"

        target_name = None
        for base_cls in cls.__mro__:
            if snake_scope in base_cls.__dict__:
                target_name = snake_scope
                break
            elif camel_scope in base_cls.__dict__:
                target_name = camel_scope
                break

        if not target_name:
            return None

        raw_attr = inspect.getattr_static(cls, target_name, None)
        if isinstance(raw_attr, (classmethod, staticmethod)):
            bound_method = getattr(cls, target_name)
            return lambda query, *args, **kwargs: bound_method(query, *args, **kwargs)

        method_attr = getattr(cls, target_name)
        if callable(method_attr):
            dummy_instance = cls()
            return lambda query, *args, **kwargs: method_attr(dummy_instance, query, *args, **kwargs)

        return None

    def _get_accessor_method(self, name: str) -> Optional[Callable]:
        snake_method = f"get_{name}_attribute"
        camel_method = f"get{self._studly_case(name)}Attribute"
        cls = self.__class__

        for base_cls in cls.__mro__:
            if snake_method in base_cls.__dict__:
                return getattr(self, snake_method)
            if camel_method in base_cls.__dict__:
                return getattr(self, camel_method)
        return None

    def _get_mutator_method(self, name: str) -> Optional[Callable]:
        snake_method = f"set_{name}_attribute"
        camel_method = f"set{self._studly_case(name)}Attribute"
        cls = self.__class__

        for base_cls in cls.__mro__:
            if snake_method in base_cls.__dict__:
                return getattr(self, snake_method)
            if camel_method in base_cls.__dict__:
                return getattr(self, camel_method)
        return None

    def _set_attribute_via_mutator(self, name: str, value: Any) -> None:
        in_mutator: set = self.__dict__["_in_mutator"]
        mutator = self._get_mutator_method(name)

        if mutator is not None and name not in in_mutator:
            in_mutator.add(name)
            try:
                before_marker = object()
                result = mutator(value)
                if result is not None or self.__dict__["_attributes"].get(name, before_marker) is before_marker:
                    self.__dict__["_attributes"][name] = result
            finally:
                in_mutator.discard(name)
        else:
            self.__dict__["_attributes"][name] = value

    def get_raw_attribute(self, name: str, default: Any = None) -> Any:
        return self.__dict__["_attributes"].get(name, default)

    def set_raw_attribute(self, name: str, value: Any) -> 'Model':
        self.__dict__["_attributes"][name] = value
        return self

    @classmethod
    def _fresh_timestamp(cls) -> str:
        return datetime.now().strftime(cls.timestamp_format)

    def _update_timestamps(self) -> None:
        if not self.timestamps:
            return
        now_str = self._fresh_timestamp()
        if not self._exists and self.created_at_column:
            if self._attributes.get(self.created_at_column) is None:
                self._attributes[self.created_at_column] = now_str
        if self.updated_at_column:
            self._attributes[self.updated_at_column] = now_str

    def touch(self) -> bool:
        if not self.timestamps:
            return False
        self._update_timestamps()
        return self.save()

    def has_many(
            self,
            related_cls: Union[Type['Model'], str],
            foreign_key: Optional[str] = None,
            local_key: Optional[str] = None
    ) -> HasMany:
        if isinstance(related_cls, str):
            related_cls = globals()[related_cls]
        fk = foreign_key or f"{self.__class__.__name__.lower()}_id"
        lk = local_key or self.primary_key
        return HasMany(related_cls, self, fk, lk)

    def hasMany(
        self,
        related_cls: Type['Model'],
        foreign_key: Optional[str] = None,
        local_key: Optional[str] = None
    ) -> HasMany:
        return self.has_many(related_cls, foreign_key, local_key)

    def morph_many(
            self,
            related_cls: Union[Type['Model'], str],
            morph_name: str
    ) -> MorphMany:
        if isinstance(related_cls, str):
            # Resolve string ke class aslinya
            related_cls = next(cls for cls in Model.__subclasses__() if cls.__name__ == related_cls)
        return MorphMany(related_cls, self, morph_name)

    def morphMany(self, related_cls: Union[Type['Model'], str], morph_name: str) -> MorphMany:
        return self.morph_many(related_cls, morph_name)

    def morph_to(self, morph_name: str) -> MorphTo:
        return MorphTo(self, morph_name)

    def morphTo(self, morph_name: str) -> MorphTo:
        return self.morph_to(morph_name)


    def belongs_to(
            self,
            related_cls: Union[Type['Model'], str],
            foreign_key: Optional[str] = None,
            owner_key: Optional[str] = None
    ) -> BelongsTo:
        if isinstance(related_cls, str):
            related_cls = globals()[related_cls]
        fk = foreign_key or f"{related_cls.__name__.lower()}_id"
        ok = owner_key or related_cls.primary_key
        return BelongsTo(related_cls, self, fk, ok)

    def belongsTo(
        self,
        related_cls: Type['Model'],
        foreign_key: Optional[str] = None,
        owner_key: Optional[str] = None
    ) -> BelongsTo:
        return self.belongs_to(related_cls, foreign_key, owner_key)

    def belongs_to_many(
            self,
            related_cls: Union[Type['Model'], str],
            pivot_table: Optional[str] = None,
            foreign_pivot_key: Optional[str] = None,
            related_pivot_key: Optional[str] = None,
            parent_key: Optional[str] = None,
            related_key: Optional[str] = None
    ) -> BelongsToMany:
        if isinstance(related_cls, str):
            related_cls = globals()[related_cls]

        # Konvensi penamaan tabel pivot ala Laravel (alfabetis, misal: role_user)
        base_name = self.__class__.__name__.lower()
        rel_name = related_cls.__name__.lower()
        default_pivot = "_".join(sorted([base_name + "s", rel_name + "s"]))  # sederhana

        p_table = pivot_table or f"{base_name}_{rel_name}"
        fp_key = foreign_pivot_key or f"{base_name}_id"
        rp_key = related_pivot_key or f"{rel_name}_id"
        p_key = parent_key or self.primary_key
        r_key = related_key or related_cls.primary_key

        return BelongsToMany(related_cls, self, p_table, fp_key, rp_key, p_key, r_key)

    def belongsToMany(
            self,
            related_cls: Union[Type['Model'], str],
            pivot_table: Optional[str] = None,
            foreign_pivot_key: Optional[str] = None,
            related_pivot_key: Optional[str] = None,
            parent_key: Optional[str] = None,
            related_key: Optional[str] = None
    ) -> BelongsToMany:
        return self.belongs_to_many(related_cls, pivot_table, foreign_pivot_key, related_pivot_key, parent_key,
                                    related_key)

    def _resolve_relation_object(self, name: str) -> Optional[Relation]:
        cls_attr = getattr(self.__class__, name, None)
        if isinstance(cls_attr, relation):
            return cls_attr.func(self)
        if callable(cls_attr):
            result = cls_attr(self)
            if isinstance(result, Relation):
                return result
        return None

    def load(self, *relations: str) -> 'Model':
        self.__class__.query().with_relations(*relations)._eager_load_relations([self])
        return self

    @classmethod
    def is_fillable(cls, key: str) -> bool:
        if cls.fillable:
            return key in cls.fillable
        if cls.guarded == ["*"]:
            return False
        return key not in cls.guarded

    @classmethod
    def _filter_fillable(cls, attributes: Dict[str, Any]) -> Dict[str, Any]:
        if not cls.fillable and cls.guarded == ["*"]:
            raise MassAssignmentError(
                f"Tambahkan properti 'fillable = [...]' pada model '{cls.__name__}' "
                f"untuk mengizinkan Mass Assignment."
            )
        return {k: v for k, v in attributes.items() if cls.is_fillable(k)}

    def fill(self, **kwargs) -> 'Model':
        filtered = self._filter_fillable(kwargs)
        for key, value in filtered.items():
            setattr(self, key, value)
        return self

    def force_fill(self, **kwargs) -> 'Model':
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

    def get_dirty(self) -> Dict[str, Any]:
        dirty = {}
        for key, value in self._attributes.items():
            if key not in self._original or self._original[key] != value:
                dirty[key] = value
        return dirty

    def is_dirty(self, *attributes: str) -> bool:
        dirty = self.get_dirty()
        if not attributes:
            return bool(dirty)
        return any(attr in dirty for attr in attributes)

    def sync_original(self) -> 'Model':
        self.__dict__["_original"] = self._attributes.copy()
        return self

    def _fire_event(self, event_name: str) -> bool:
        """Memicu event hook internal model dan Observer eksternal."""
        # 1. Eksekusi Hook dari dalam Model (Internal)
        hook = getattr(self, event_name, None)
        if callable(hook):
            result = hook()
            if result is False:
                return False

        # 2. Eksekusi Hook dari Observers Eksternal yang terdaftar
        model_name = self.__class__.__name__
        observers = self._observers_registry.get(model_name, [])

        for observer in observers:
            obs_hook = getattr(observer, event_name, None)
            if callable(obs_hook):
                # Suntikkan instance model ini (self) ke dalam observer
                result = obs_hook(self)
                if result is False:
                    return False
        return True

    @classmethod
    def create(cls, **kwargs) -> 'Model':
        instance = cls(**kwargs)
        instance.save()
        return instance

    def save(self) -> bool:
        if self._fire_event("before_save") is False:
            return False

        if not self._exists:
            if self._fire_event("before_create") is False:
                return False
        else:
            if self._fire_event("before_update") is False:
                return False

        conn = DatabaseManager.get_connection(self.connection_name)
        cursor = conn.cursor()
        table = self.get_table_name()
        pk = self.primary_key

        if not self._exists:
            if self.timestamps:
                self._update_timestamps()

            if not self._attributes:
                return False

            columns = list(self._attributes.keys())
            placeholders = ", ".join(["?"] * len(columns))
            col_names = ", ".join(columns)
            values = [self._attributes[col] for col in columns]

            sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            conn.commit()

            if pk not in self._attributes and cursor.lastrowid:
                self._attributes[pk] = cursor.lastrowid

            self.__dict__["_exists"] = True
            self.sync_original()

            self._fire_event("after_create")
            self._fire_event("after_save")
            return True

        else:
            dirty = self.get_dirty()
            if not dirty:
                return True

            if self.timestamps:
                self._update_timestamps()
                dirty = self.get_dirty()

            if pk not in self._original and pk not in self._attributes:
                raise ValueError(
                    f"Tidak dapat melakukan update pada '{self.__class__.__name__}' tanpa nilai primary key '{pk}'."
                )

            pk_val = self._original.get(pk, self._attributes.get(pk))
            set_clause = ", ".join([f"{col} = ?" for col in dirty.keys()])
            values = list(dirty.values()) + [pk_val]

            sql = f"UPDATE {table} SET {set_clause} WHERE {pk} = ?"
            cursor.execute(sql, values)
            conn.commit()

            self.sync_original()

            self._fire_event("after_update")
            self._fire_event("after_save")
            return True

    def update(self, **kwargs) -> bool:
        return self.fill(**kwargs).save()

    def trashed(self) -> bool:
        if not self.soft_deletes:
            return False
        return getattr(self, self.deleted_at_column) is not None

    def delete(self) -> bool:
        if not self._exists:
            return False

        if self._fire_event("before_delete") is False:
            return False

        pk = self.primary_key
        pk_val = self._original.get(pk, self._attributes.get(pk))
        if pk_val is None:
            raise ValueError(
                f"Tidak dapat menghapus '{self.__class__.__name__}' karena primary key '{pk}' bernilai None."
            )

        conn = DatabaseManager.get_connection(self.connection_name)
        cursor = conn.cursor()
        table = self.get_table_name()

        if self.soft_deletes:
            del_col = self.deleted_at_column
            now_str = self._fresh_timestamp()
            set_cols = [f"{del_col} = ?"]
            params = [now_str]

            self._attributes[del_col] = now_str

            if self.timestamps and self.updated_at_column:
                set_cols.append(f"{self.updated_at_column} = ?")
                params.append(now_str)
                self._attributes[self.updated_at_column] = now_str

            params.append(pk_val)
            sql = f"UPDATE {table} SET {', '.join(set_cols)} WHERE {pk} = ?"
            cursor.execute(sql, tuple(params))
            conn.commit()

            self.sync_original()
        else:
            sql = f"DELETE FROM {table} WHERE {pk} = ?"
            cursor.execute(sql, (pk_val,))
            conn.commit()
            self.__dict__["_exists"] = False

        self._fire_event("after_delete")
        return True

    def force_delete(self) -> bool:
        if not self._exists:
            return False

        if self._fire_event("before_delete") is False:
            return False

        pk = self.primary_key
        pk_val = self._original.get(pk, self._attributes.get(pk))
        if pk_val is None:
            raise ValueError(
                f"Tidak dapat menghapus '{self.__class__.__name__}' karena primary key '{pk}' bernilai None."
            )

        conn = DatabaseManager.get_connection(self.connection_name)
        cursor = conn.cursor()
        table = self.get_table_name()

        sql = f"DELETE FROM {table} WHERE {pk} = ?"
        cursor.execute(sql, (pk_val,))
        conn.commit()

        self.__dict__["_exists"] = False
        self._fire_event("after_delete")
        return True

    def forceDelete(self) -> bool:
        return self.force_delete()

    def restore(self) -> bool:
        if not self.soft_deletes or not self._exists:
            return False

        if self._fire_event("before_restore") is False:
            return False

        pk = self.primary_key
        pk_val = self._original.get(pk, self._attributes.get(pk))
        del_col = self.deleted_at_column

        conn = DatabaseManager.get_connection(self.connection_name)
        cursor = conn.cursor()
        table = self.get_table_name()

        set_cols = [f"{del_col} = NULL"]
        params: List[Any] = []
        self._attributes[del_col] = None

        if self.timestamps and self.updated_at_column:
            now_str = self._fresh_timestamp()
            set_cols.append(f"{self.updated_at_column} = ?")
            params.append(now_str)
            self._attributes[self.updated_at_column] = now_str

        params.append(pk_val)
        sql = f"UPDATE {table} SET {', '.join(set_cols)} WHERE {pk} = ?"
        cursor.execute(sql, tuple(params))
        conn.commit()

        self.sync_original()

        self._fire_event("after_restore")
        return True

    @classmethod
    def destroy(cls, *ids: Any) -> int:
        count = 0
        for pk_val in ids:
            instance = cls.find(pk_val)
            if instance and instance.delete():
                count += 1
        return count

    @classmethod
    def _hydrate(cls, row_dict: dict) -> 'Model':
        instance = cls()
        instance.__dict__["_attributes"] = row_dict.copy()
        instance.__dict__["_original"] = row_dict.copy()
        instance.__dict__["_relations"] = {}
        instance.__dict__["_exists"] = True
        return instance

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_"):
            cls = object.__getattribute__(self, "__class__")
            cls_attr = getattr(cls, name, None)

            if isinstance(cls_attr, relation):
                return cls_attr.__get__(self, cls)

            d = object.__getattribute__(self, "__dict__")
            relations = d.get("_relations", {})
            if name in relations:
                cached = relations[name]
                if isinstance(cached, list) and callable(cls_attr):
                    return _RelationList(cached, lambda: cls_attr(self))
                if isinstance(cached, Model) and callable(cls_attr):
                    cached.__dict__["_relation_factory"] = lambda: cls_attr(self)
                return cached

        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' tidak memiliki atribut internal '{name}'")

        attributes = self.__dict__.get("_attributes", {})
        raw_value = attributes.get(name, None)

        accessor = self._get_accessor_method(name)
        if accessor is not None:
            return accessor(raw_value)

        if name in attributes:
            return raw_value

        relations = self.__dict__.get("_relations", {})
        if name in relations:
            return relations[name]

        return None

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name in self._RESERVED_CLASS_ATTRS:
            super().__setattr__(name, value)
        else:
            self._set_attribute_via_mutator(name, value)

    def to_dict(self) -> dict:
        data = {}
        for key in self.__dict__["_attributes"].keys():
            data[key] = getattr(self, key)

        for appended_key in getattr(self, "appends", []):
            data[appended_key] = getattr(self, appended_key)

        for rel_name, rel_val in self.__dict__["_relations"].items():
            if isinstance(rel_val, list):
                data[rel_name] = [item.to_dict() for item in rel_val]
            elif isinstance(rel_val, Model):
                data[rel_name] = rel_val.to_dict()
            else:
                data[rel_name] = rel_val
        return data

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self._attributes.items())
        if self._relations:
            rels = ", ".join(f"{k}={v!r}" for k, v in self._relations.items())
            attrs = f"{attrs}, relations={{{rels}}}" if attrs else f"relations={{{rels}}}"
        return f"<{self.__class__.__name__}({attrs})>"

    @classmethod
    def observe(cls, observer_cls: Type) -> None:
        """Mendaftarkan class Observer ke Model ini."""
        model_name = cls.__name__
        if model_name not in Model._observers_registry:
            Model._observers_registry[model_name] = []
        # Simpan instance dari observer
        Model._observers_registry[model_name].append(observer_cls())