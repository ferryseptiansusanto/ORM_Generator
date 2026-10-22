import os
import sys  # Tambahkan sys untuk membaca argumen terminal
from database_manager import DatabaseManager

def run_migration():
    db_file = "app.db"

    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"[INFO] Database lama '{db_file}' dihapus.")

    conn = DatabaseManager.get_connection("default")
    cursor = conn.cursor()

    # --- PERUBAHAN DI SINI ---
    # Cek apakah user memasukkan argumen file SQL di terminal
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]  # Mengambil argumen pertama (database.sql)
    else:
        # Default jika tidak ada argumen (mencari di folder yang sama)
        sql_file = os.path.join(os.path.dirname(__file__), "database.sql")

    print(f"[INFO] Membaca file SQL dari: {sql_file}")
    print("[INFO] Membuat tabel-tabel database...")

    # Baca seluruh isi file SQL
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_script = f.read()

    cursor.executescript(sql_script)
    conn.commit()
    print("[OK] Migrasi tabel berhasil! Database 'app.db' siap digunakan.")

if __name__ == "__main__":
    run_migration()