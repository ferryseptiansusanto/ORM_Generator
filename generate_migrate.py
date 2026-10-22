import os
import sys
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from database_manager import DatabaseManager

def run_migration():
    # 1. Cek argumen file SQL dari terminal
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]  # Mengambil 'database/database.sql'
    else:
        sql_file = os.path.join(os.path.dirname(__file__), "database.sql")

    # 2. Ambil lokasi folder dari file SQL tersebut
    # Jika sql_file = "database/database.sql", maka sql_dir = "database"
    sql_dir = os.path.dirname(sql_file)

    # 3. Tentukan path target app.db di dalam folder tersebut
    # Hasilnya akan menjadi: "database/app.db"
    db_file = os.path.join(sql_dir, "app.db") if sql_dir else "app.db"

    # Hapus file database lama jika ingin reset bersih dari awal
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"[INFO] Database lama '{db_file}' dihapus.")

    print(f"[INFO] Membaca file SQL dari: {sql_file}")
    print(f"[INFO] File database baru akan dibuat di: {db_file}")

    # Pindah direktori kerja aktif ke folder tempat sql berada (folder 'database')
    old_cwd = os.getcwd()
    if sql_dir:
        os.chdir(sql_dir)

    # --- CATATAN PENTING ---
    # Pastikan DatabaseManager menerima path dinamis 'db_file' ini.
    # Jika get_connection("default") Anda membaca konfigurasi statis dari database_config.py,
    # Anda mungkin perlu menyesuaikan database_config.py agar menggunakan path dinamis ini,
    # atau override konfigurasinya di sini jika method get_connection mendukungnya.
    try:
        conn = DatabaseManager.get_connection("default")
        cursor = conn.cursor()

        print("[INFO] Membuat tabel-tabel database...")
        abs_sql_file = os.path.abspath(os.path.join(old_cwd, sql_file))
        # Baca seluruh isi file SQL
        with open(abs_sql_file, "r", encoding="utf-8") as f:
            sql_script = f.read()

        # Jalankan seluruh script SQL
        cursor.executescript(sql_script)

        conn.commit()
    finally:
        # Kembalikan posisi direktori kerja ke folder utama setelah selesai
        os.chdir(old_cwd)

    print(f"[OK] Migrasi tabel berhasil! Database '{db_file}' siap digunakan.")

if __name__ == "__main__":
    run_migration()