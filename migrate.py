# migrate.py
import os
from database_manager import DatabaseManager
# migrate.py

def run_migration():
    db_file = "app.db"

    # Hapus file database lama jika ingin reset bersih dari awal
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"[INFO] Database lama '{db_file}' dihapus.")

    # Ambil koneksi (otomatis membuat file app.db baru)
    conn = DatabaseManager.get_connection("default")
    cursor = conn.cursor()

    print("[INFO] Membuat tabel-tabel database...")

    # 1. Tabel Users (Dilengkapi Timestamps & Soft Deletes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT,
        deleted_at TEXT
    );
    """)

    # 2. Tabel Posts (Memiliki foreign key ke users -> relasi has_many / belongs_to)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        body TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 3. Tabel Roles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT
    );
    """)

    # 4. Tabel Pivot role_user (Many-to-Many antara users dan roles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
    );
    

    
    """)

    # 1. Tabel Transactions / Timbangan
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_code TEXT NOT NULL,
            plate_number TEXT NOT NULL,
            net_weight REAL,
            created_at TEXT,
            updated_at TEXT
        );
        """)

    # 2. Membuat INDEX untuk mempercepat pencarian plat nomor dan tanggal
    # Index tunggal untuk plate_number (pencarian teks / LIKE)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_plate ON transactions(plate_number);
        """)

    # Index tunggal untuk created_at (filter rentang tanggal / sorting)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
        """)

    # (Opsional) Jika sering mencari kombinasi plat nomor DAN tanggal sekaligus,
    # Anda juga bisa membuat Index Gabungan (Composite Index):
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_plate_date ON transactions(plate_number, created_at);
        """)



    conn.commit()
    print("[OK] Migrasi tabel berhasil! Database 'app.db' siap digunakan.")



if __name__ == "__main__":
    run_migration()