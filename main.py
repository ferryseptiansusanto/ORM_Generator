# main.py
import importlib
from database_manager import DatabaseManager
from orm_generator import ORMGenerator

# 1. Setup Database & Bersihkan tabel lama
conn = DatabaseManager.get_connection("default")
conn.executescript("""
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS categories;

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
""")
conn.commit()

# 2. Jalankan Generator untuk membuat file models.py
generator = ORMGenerator(connection_name="default", output_filename="models.py")
generator.generate()

# 3. Import atau Reload models agar aman dari cache lama
import models
importlib.reload(models)
from models import Category, Product

print("\n--- TEST RELASI BELONGS_TO & HAS_MANY ---")

# 4. Uji interaksi ORM
elektronik = Category.create(name="Elektronik")
p1 = Product.create(category_id=elektronik.id, name="Smartphone Android", price=3500000)

print("Kategori Ter-generate:", elektronik.name)
print("Produk milik Kategori (HasMany):", [p.name for p in elektronik.products])

# 5. Uji BelongsTo
print("--- DEBUGGING BELONGSTO ---")
print("Isi _attributes p1:", p1._attributes)
print("Nilai p1.category_id:", p1.category_id)
print("Hasil pemanggilan langsung Category.find(p1.category_id):", Category.find(p1.category_id))
print("Hasil pemanggilan p1.category:", p1.category)
print("Kategori dari Produk (BelongsTo):", p1.category.name)