# demo_pivot.py
from database_manager import DatabaseManager
from eloquent_base import Model, relation


# 1. Definisi Model dengan Relasi Many-to-Many
class User(Model):
    table = "users"
    fillable = ["name"]

    @relation
    def roles(self):
        return self.belongs_to_many(
            Role,
            pivot_table="role_user",
            foreign_pivot_key="user_id",
            related_pivot_key="role_id"
        )


class Role(Model):
    table = "roles"
    fillable = ["name"]

    @relation
    def users(self):
        return self.belongs_to_many(
            User,
            pivot_table="role_user",
            foreign_pivot_key="role_id",
            related_pivot_key="user_id"
        )


# 2. Setup Database & Bersihkan Tabel Lama (Mencegah Error Table Already Exists)
conn = DatabaseManager.get_connection("default")
conn.executescript("""
    DROP TABLE IF EXISTS role_user;
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS roles;

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT
    );

    CREATE TABLE roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT
    );

    CREATE TABLE role_user (
        user_id INTEGER,
        role_id INTEGER,
        PRIMARY KEY (user_id, role_id)
    );
""")
conn.commit()

print("=== 1. TEST SEED DATA & .attach() ===")
# Buat data dummy
user = User.create(name="Budi Santoso")
admin_role = Role.create(name="Admin")
editor_role = Role.create(name="Editor")
viewer_role = Role.create(name="Viewer")

# Menggunakan .attach() dengan objek Model dan ID langsung
user.roles.attach(admin_role)
user.roles.attach(editor_role.id)

print(f"Role milik {user.name} setelah attach (Admin & Editor):", [r.name for r in user.roles])

print("\n=== 2. TEST .detach() ===")
# Menghapus relasi tertentu dari tabel pivot
user.roles.detach(admin_role)
print(f"Role milik {user.name} setelah detach Admin:", [r.name for r in user.roles])

print("\n=== 3. TEST .sync() ===")
# Menyelaraskan relasi: Hanya menyisakan Viewer & Editor, menghapus yang lain
user.roles.sync([editor_role.id, viewer_role.id])
print(f"Role milik {user.name} setelah sync ([Editor, Viewer]):", [r.name for r in user.roles])


# Memaksa query baru langsung ke database (bypass cache memori)
print(f"Role milik {user.name} setelah attach:", [r.name for r in user.roles().get()])

user = User.create(name="Budi Santoso")
print(f"DEBUG: ID User yang baru dibuat = {user.id}") # Pastikan ini tidak None!