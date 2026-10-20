# demo_crud.py
from database_manager import DatabaseManager
from eloquent_base import Model

# 1. Definisi Model dengan Mass Assignment Protection
class User(Model):
    table = "users"
    primary_key = "id"
    # Hanya 'name', 'email', dan 'age' yang boleh diisi secara massal!
    # Kolom 'is_admin' sengaja TIDAK dimasukkan ke fillable demi keamanan.
    fillable = ["name", "email", "age"]

# 2. Buat skema tabel di SQLite in-memory
conn = DatabaseManager.get_connection("default")
conn.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        age INTEGER,
        is_admin INTEGER DEFAULT 0
    )
""")
conn.commit()

print("=== 1. TEST CREATE & MASS ASSIGNMENT PROTECTION ===")
# User nakal mencoba mengirim is_admin=1 lewat payload mass assignment
user1 = User.create(
    name="Budi Santoso",
    email="budi@mail.com",
    age=25,
    is_admin=1  # <-- Akan diabaikan otomatis karena tidak ada di fillable!
)
print("Hasil User.create():", user1)
print("Cek dari DB langsung:", User.find(user1.id))  # is_admin tetap 0 (default DB)

print("\n=== 2. TEST SAVE() MANUAL (ACTIVE RECORD) ===")
# Jika diubah secara eksplisit lewat atribut objek, is_admin diizinkan berubah
user2 = User(name="Citra Lestari", email="citra@mail.com", age=29)
user2.is_admin = 1  # Assignment eksplisit (bukan mass assignment)
user2.save()
print("Hasil save() manual :", User.find(user2.id))

print("\n=== 3. TEST UPDATE() & DIRTY TRACKING ===")
# Mengubah sebagian atribut dengan .update()
user1.update(age=26, name="Budi S. (Updated)", is_admin=1)  # is_admin=1 tetap diabaikan
print("Setelah user1.update():", User.find(user1.id))

print("\n=== 4. TEST BULK UPDATE VIA QUERY BUILDER ===")
User.create(name="remaja1", email="r1@mail.com", age=16)
User.create(name="remaja2", email="r2@mail.com", age=17)

# Update massal menggunakan chaining .where().update()
affected = User.where("age", "<", 18).update(age=18)
print(f"Jumlah baris ter-update: {affected}")
print("Semua data saat ini:", User.all())

print("\n=== 5. TEST DELETE (INSTANCE & BULK DELETE) ===")
# Hapus lewat instance
user2.delete()
print("Setelah user2.delete(), sisa total user:", User.count())

# Hapus massal lewat QueryBuilder
deleted_count = User.where("age", "=", 18).delete()
print(f"Bulk delete berhasil menghapus {deleted_count} baris.")
print("Data tersisa di tabel:", User.all())