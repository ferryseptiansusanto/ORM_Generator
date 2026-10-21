# 🚀 Laravel-Style Custom Python ORM & Generator

Custom ORM berbasis Python berarsitektur **Active Record Pattern** yang dirancang secara presisi untuk meniru
sintaks, pola, dan fitur ekspresif milik **Laravel Eloquent** secara *native* di Python
(tanpa dependensi berat pihak ketiga kecuali driver database dasar).

## 📂 Struktur Direktori Proyek
File inti yang wajib ada dalam proyek ini:
└── ferryseptiansusanto-orm_generator/
    ├── database_config.py      # Konfigurasi terpusat multi-database
    ├── database_manager.py     # Connection pooler & manajemen transaksi (DB)
    ├── eloquent_base.py        # Core Engine (Model, QueryBuilder, Collection, Relations, Observers)
    ├── orm_generator.py        # Modul Reverse Engineering (Introspeksi skema otomatis)
    ├── migrate.py              # Skrip migrasi skema awal & index database
    └── main.py                 # Entry point untuk generate file models.py

🌟 Ringkasan Kapabilitas & Fitur ORM
1. Manajemen Multi-Database & Dynamic Switching
Multi-Driver Support: Mendukung koneksi langsung ke SQLite, PostgreSQL, dan MySQL.

Dynamic Connection (from_connection): Memindahkan koneksi database model secara on-the-fly saat runtime tanpa mengubah definisi class (contoh: User.from_connection("pg_connection").all()).

2. Operasi CRUD & Mass Assignment Protection
Create, Read, Update, Delete: Operasi data instan via Model.create(**kwargs), Model.find(id), user.save(), user.update(), dan user.delete().

Mass Assignment Security: Melindungi model dari injeksi atribut liar menggunakan daftar putih fillable = [...] (melemparkan MassAssignmentError jika dilanggar).

Dirty Tracking: Mekanisme pemantauan perubahan atribut (get_dirty()) sehingga kueri UPDATE hanya mengeksekusi kolom yang benar-benar berubah.

3. Database Transactions (DB.transaction)
ORM ini mendukung transaksi tingkat lanjut dengan pendekatan ACID (Atomicity, Consistency, Isolation, Durability) menggunakan Context Manager bergaya Laravel DB::transaction():

Otomatis membuka transaksi saat masuk ke blok with DB.transaction():.

Otomatis melakukan commit() jika seluruh operasi berhasil tanpa error.

Otomatis melakukan rollback() dan membatalkan seluruh perubahan jika terjadi Exception di tengah jalan.

4. Fluent Query Builder & Method Chaining
Mendukung perakitan kueri berantai (method chaining) dalam gaya snake_case maupun camelCase:

Filtering: .select(), .where(), .or_where(), .where_in(), .where_null().

Sorting & Limiting: .order_by(), .limit() / .take(), .offset() / .skip().

Pagination Siap Pakai: .paginate(per_page=15, page=1) mengembalikan kamus metadata lengkap (data, current_page, last_page, total, from, to).

5. Arsitektur Relasi Lengkap (Lazy & Eager Loading)
One-to-Many & Inverse: has_many dan belongs_to (mendukung lazy loading saat diakses sebagai properti maupun query chaining saat dipanggil sebagai method).

Many-to-Many (Pivot Tables): belongs_to_many lengkap dengan metode .attach(), .detach(), dan .sync(), serta pembersihan cache otomatis.

Polymorphic Relations: morph_many dan morph_to untuk menghubungkan satu tabel anak ke berbagai model induk secara dinamis.

Eager Loading (Anti N+1): Memuat relasi di awal dengan .with_relations("posts.comments", "roles") atau alias .with_("posts").

6. Otomasi Siklus Hidup (Timestamps & Soft Deletes)
Automatic Timestamps: Otomatis mengisi dan memperbarui kolom created_at dan updated_at.

Soft Deletes: Menyembunyikan data terhapus secara otomatis (deleted_at), dengan opsi modifier .with_trashed(), .only_trashed(), .restore(), dan .force_delete().

7. Transformasi Data & Model Observers
Accessors & Mutators: Mencegat pembacaan/penulisan kolom via get_<attr>_attribute dan set_<attr>_attribute.

Query Scopes: Membuat shortcut filter kueri dengan awalan scope_<nama>().

Observers: Memisahkan logika lifecycle hooks (before_create, after_delete, dll.) ke dalam class Observer terpisah.



Berikut adalah **Panduan Langkah Demi Langkah Penggunaan Custom ORM** ini secara end-to-end:

### 1. Setup Konfigurasi Database (`database_config.py`)
Pastikan kredensial database Anda sudah terdaftar dengan benar. Secara default, sistem mendukung SQLite (`app.db`), PostgreSQL, dan MySQL.

# database_config.py
DATABASES = {
    "default": {
        "driver": "sqlite",
        "database": "app.db",
    }
}



### 2. Jalankan Migrasi Skema (`migrate.py`)
Buat skrip migrasi untuk membuat tabel-tabel awal di database (misalnya tabel `users`, `categories`, `products`, `roles`, dan tabel pivot `role_user`).

# migrate.py
from database_manager import DatabaseManager

conn = DatabaseManager.get_connection("default")
conn.executescript("""
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS categories;
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS roles;
    DROP TABLE IF EXISTS role_user;

    CREATE TABLE categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        created_at DATETIME,
        updated_at DATETIME
    );

    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT,
        price INTEGER,
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME
    );

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        created_at DATETIME,
        updated_at DATETIME
    );

    CREATE TABLE roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        created_at DATETIME,
        updated_at DATETIME
    );

    CREATE TABLE role_user (
        user_id INTEGER,
        role_id INTEGER,
        PRIMARY KEY (user_id, role_id)
    );
""")
conn.commit()
print("[OK] Migrasi database berhasil!")


### 3. Generate File Model Otomatis (`main.py`)
Gunakan `ORMGenerator` untuk membaca skema tabel database secara instan dan men-generate file `models.py` lengkap dengan relasinya (*has_many*, *belongs_to*, *belongs_to_many*).

# main.py
import importlib
from orm_generator import ORMGenerator

if __name__ == "__main__":
    # 1. Jalankan generator reverse engineering
    generator = ORMGenerator(connection_name="default", output_filename="models.py")
    generator.generate()

    # 2. Reload modul models agar siap di-import
    import models
    importlib.reload(models)

    print("[OK] File models.py berhasil dibuat dan siap digunakan!")


### 4. Cara Menggunakan Model di Aplikasi (`main.py` atau Skrip Utama)

Setelah `models.py` terbentuk, Anda bisa langsung mengimpor kelas model tersebut dan menikmati fitur ala Laravel Eloquent:

#### A. Operasi CRUD & Mass Assignment

from models import Category, Product

# --- CREATE (Otomatis mengisi created_at & updated_at) ---
elektronik = Category.create(name="Elektronik")

# --- READ (Method Chaining & Query Builder) ---
# Mencari data dengan filter berantai
products = Product.where("price", ">", 1000000).order_by("price", "DESC").get()

# Mencari berdasarkan Primary Key
kat = Category.find(1)

# --- UPDATE ---
elektronik.name = "Elektronik & Gadget"
elektronik.save()

# --- DELETE & SOFT DELETES ---
# Jika model mengaktifkan soft_deletes, data hanya mengisi kolom 'deleted_at'
prod = Product.find(1)
prod.delete()

# Mengambil data yang sudah di-soft-delete saja
trashed = Product.only_trashed().get()


#### B. Mengakses Relasi (Lazy & Eager Loading)
# 1. Lazy Loading (Otomatis mengambil data terkait saat properti dipanggil)
print(f"Produk dalam kategori {elektronik.name}:")
for p in elektronik.products:  # Memanggil relasi has_many
    print(f" - {p.name} (Kategori: {p.category.name})") # Memanggil relasi belongs_to

# 2. Eager Loading (Mencegah masalah N+1 Query)
categories_with_products = Category.with_("products").all()



#### C. Mengelola Relasi Many-to-Many (Pivot Table)
from models import User, Role

user = User.create(name="Budi Santoso")
admin_role = Role.create(name="Admin")

# Menambahkan relasi pivot
user.roles.attach(admin_role)

# Menghapus relasi pivot
user.roles.detach(admin_role.id)

# Menyinkronkan daftar ID role secara mutlak
user.roles.sync([1, 2, 3])











Berikut adalah ringkasan kapabilitas dan fungsi penggunaan yang dapat dilakukan oleh ORM ini:

---

## 1. Peran & Fungsi Tiap Modul Inti

| Nama Modul | Fungsi Utama |
| --- | --- |
| **`database_config.py`** | Menyimpan dictionary konfigurasi terpusat (`DATABASES`) untuk mendukung multi-database (`sqlite`, `postgresql`, `mysql`).

 |
| **`database_manager.py`** | Bertindak sebagai *Connection Pooler* yang mengelola siklus hidup koneksi (`get_connection()`, `close_all()`) dan menyeragamkan output baris database menjadi format *dictionary-like* (`sqlite3.Row`, `RealDictCursor`, `DictCursor`).

 |
| **`eloquent_base.py`** | *Core Engine* ORM yang memuat `Model` (dengan `ModelMeta`), `QueryBuilder`, `Collection`, sistem *Relationships*, *Events/Observers*, *Soft Deletes*, serta *Accessors & Mutators*.

 |
| **`orm_generator.py`** | Modul *Reverse Engineering* otomatis untuk mengintrospeksi skema tabel database dan men-generate kode class model Python (`models.py`) lengkap dengan relasinya.

 |
| **`migrate.py`** | Skrip pembuatan skema tabel awal (`users`, `posts`, `roles`, `role_user`, `transactions`) beserta pembuatan *Single & Composite Index* SQL.

 |
| **`main.py`** | *Entry point* untuk mengeksekusi `ORMGenerator` guna menghasilkan file `models.py` secara instan dari skema database aktif.

 |

---

## 2. Kapabilitas & Fitur Penggunaan ORM

### A. Manajemen Multi-Database & Dynamic Switching

* **Multi-Driver Support:** Mendukung koneksi langsung ke SQLite, PostgreSQL, dan MySQL.


* **Dynamic Connection (`from_connection`):** Setiap model dapat berpindah koneksi database secara *on-the-fly* saat *runtime* tanpa mengubah definisi class asli menggunakan `User.from_connection("pg_connection").all()`.



### B. Operasi CRUD & Mass Assignment Protection

* **Create:** Membuat dan menyimpan data dalam satu baris perintah dengan `Model.create(**kwargs)` atau instansiasi bertahap `m = Model(**kwargs); m.save()`.


* **Read:** Mengambil seluruh data (`Model.all()`), mencari berdasarkan Primary Key (`Model.find(id)`), atau mengambil baris pertama (`Model.where(...).first()`).


* **Update & Dirty Tracking:** Memperbarui data per instance (`user.update(...)` atau `user.save()`) maupun *mass update* langsung dari kueri (`User.where(...).update(...)`). Dilengkapi pelacakan perubahan atribut (`get_dirty()`, `is_dirty()`) sehingga kueri `UPDATE` hanya mengeksekusi kolom yang nilainya berubah.


* **Delete & Destroy:** Menghapus lewat instance (`user.delete()`) atau menghapus banyak ID sekaligus (`User.destroy(1, 2, 3)`).
* **Mass Assignment Security:** Melindungi model dari injeksi atribut liar menggunakan daftar `fillable = [...]` dan `guarded = ["*"]` (melempar `MassAssignmentError` jika tidak dikonfigurasi), serta menyediakan `force_fill()` untuk mem-bypass proteksi secara internal.



### C. Fluent Query Builder & Method Chaining

Berkat delegasi `ModelMeta`, metode `QueryBuilder` dapat dipanggil langsung dari class `Model` secara berantai (*method chaining*) dalam gaya *snake_case* maupun *camelCase*:

* **Filtering:** `.select()`, `.where()`, `.or_where()` / `.orWhere()`, `.where_in()` / `.whereIn()`, `.where_null()`, `.where_not_null()`.
* **Pencarian Cepat & Tanggal:** `.search(column, keyword)` untuk filter `LIKE %keyword%` otomatis, dan `.where_date_between(col, start, end)` untuk rentang tanggal.


* **Sorting & Limiting:** `.order_by()` / `.orderBy()`, `.limit()` / `.take()`, dan `.offset()` / `.skip()`.
* **Agregasi & Eksekusi:** `.count()`, `.get()`, `.first()`, `.find()`, dan `.pluck(column)`.
* **Pagination Siap Pakai:** `.paginate(per_page=15, page=1)` yang otomatis menghitung total baris, membatasi offset/limit, dan mengembalikan *dictionary* metadata halaman lengkap (`data`, `current_page`, `last_page`, `total`, `from`, `to`).



### D. Arsitektur Relasi Lengkap (Lazy & Eager Loading)

Menggunakan dekorator `@relation` yang cerdas:

* **One-to-Many & Inverse (`has_many` & `belongs_to`):** Mendukung *Lazy Loading* saat diakses sebagai properti (`user.posts`, `post.user`) dan *Relation Query Chaining* saat dipanggil sebagai method (`user.posts().where(...).get()`).


* **Many-to-Many (`belongs_to_many`):** Mengelola tabel perantara (*pivot table*) lengkap dengan operasi `.attach()`, `.detach()`, dan `.sync()` yang otomatis membersihkan *cache* relasi di memori.


* **Polymorphic Relations (`morph_many` & `morph_to`):** Memungkinkan satu tabel anak (misal `comments`) berelasi dengan berbagai jenis model induk menggunakan pasangan kolom `<name>_id` dan `<name>_type`.


* **Eager Loading (Anti N+1 Query Problem):** Memuat relasi di awal kueri (termasuk *nested relations* dengan *dot notation*) menggunakan `.with_relations("posts.comments", "roles")` atau alias `.with_("posts")`, serta *Lazy Eager Loading* pada instance aktif via `user.load("posts")`.



### E. Otomasi Siklus Hidup Model (Timestamps & Soft Deletes)

* **Automatic Timestamps:** Jika `timestamps = True`, ORM otomatis mengisi `created_at` dan `updated_at` saat insert, memperbarui `updated_at` saat update, serta menyediakan metode `model.touch()`.


* **Soft Deletes:** Jika `soft_deletes = True`, pemanggilan `.delete()` tidak menghapus baris dari database melainkan mengisi kolom `deleted_at`. Kueri normal otomatis menyembunyikan data terhapus, namun dapat diakses kembali menggunakan modifier `.with_trashed()`, `.only_trashed()`, dipulihkan dengan `.restore()`, atau dihapus permanen dengan `.force_delete()`.



### F. Transformasi Data & Kueri Kustom (Accessors, Mutators, Scopes)

* **Accessors (Getter):** Memformat nilai atribut secara otomatis saat dibaca dengan mendefinisikan `get_<nama>_attribute(self, value)` atau `get<StudlyName>Attribute`. Mendukung penyisipan atribut virtual ke JSON/dict melalui properti `appends = [...]`.


* **Mutators (Setter):** Memodifikasi atau mengenkripsi data sesaat sebelum disimpan ke dalam `_attributes` dengan mendefinisikan `set_<nama>_attribute(self, value)`.


* **Local Query Scopes:** Membuat *shortcut* filter kueri yang dapat dipakai ulang cukup dengan membuat method berawalan `scope_<nama>(self, query, ...)` (misal `scope_active` dipanggil via `User.active().get()`).



### G. Model Events, Hooks & External Observers

* **Internal Lifecycle Hooks:** Mencegat siklus hidup data langsung di dalam class Model menggunakan method `before_save`, `after_save`, `before_create`, `after_create`, `before_update`, `after_update`, `before_delete`, `after_delete`, `before_restore`, dan `after_restore`. Mengembalikan `False` pada hook `before_*` akan otomatis membatalkan operasi database.


* **Observer Pattern:** Memisahkan logika event ke class terpisah dan mendaftarkannya melalui `User.observe(UserObserver)`.



### H. In-Memory Collection & Reverse Engineering Generator

* **Custom `Collection`:** Hasil `.get()` dibungkus dalam objek turunan `list` bergaya Laravel Collection yang mendukung manipulasi memori secara ekspresif: `.where()`, `.filter()`, `.map()`, `.group_by()`, `.pluck()`, `.first()`, `.last()`, dan serialisasi rekursif `.to_dict()`.


* **Smart `ORMGenerator`:** Membaca struktur tabel secara otomatis, mengubah nama tabel *plural snake_case* menjadi class *singular StudlyCase* (termasuk kata tidak beraturan seperti `categories` -> `Category`), mendeteksi `fillable`, `timestamps`, `soft_deletes`, merangkai relasi `has_many` & `belongs_to`, mengubah tabel pivot murni menjadi relasi `belongs_to_many`, hingga mendeteksi kolom polimorfik (`morph_to` & petunjuk `morph_many`).



---