# demo_events.py
from database_manager import DatabaseManager
from eloquent_base import Model

class Article(Model):
    table = "articles"
    fillable = ["title", "slug", "status"]

    # --- Model Event Hooks ---
    def before_create(self):
        print(f"[Event] before_create dipanggil untuk artikel: {self.title}")
        # Otomatis buat slug sederhana dari title jika belum ada
        if not self.slug:
            self.slug = self.title.lower().replace(" ", "-")

    def after_save(self):
        print(f"[Event] after_save berhasil dieksekusi untuk ID: {self.id}")

    def before_delete(self):
        print(f"[Event] before_delete dipanggil untuk ID: {self.id}")
        # Contoh validasi: Cegah penghapusan jika status artikel masih 'published'
        if self.status == "published":
            print("[Event] DIBATALKAN! Artikel berstatus 'published' tidak boleh dihapus.")
            return False # Mengembalikan False akan menghentikan proses delete()!


# Setup tabel SQLite
conn = DatabaseManager.get_connection("default")
conn.execute("""
    CREATE TABLE articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        slug TEXT,
        status TEXT
    )
""")
conn.commit()

print("=== 1. TEST BEFORE_CREATE & AFTER_SAVE ===")
art1 = Article.create(title="Belajar Model Events", status="draft")
print("Hasil Artikel tersimpan:", art1)

print("\n=== 2. TEST BEFORE_DELETE DENGAN PENGGAGALAN (RETURN FALSE) ===")
# Ubah status menjadi published agar memicu proteksi before_delete
art1.update(status="published")

# Coba hapus
berhasil_hapus = art1.delete()
print("Apakah penghapusan berhasil?", berhasil_hapus)
print("Apakah data masih ada di database?", Article.find(art1.id) is not None)