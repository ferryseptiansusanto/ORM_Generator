File inti yang wajib ada hanyalah:

database_config.py

database_manager.py

eloquent_base.py

orm_generator.py

migrate.py & main.py (yang akan menghasilkan models.py).



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