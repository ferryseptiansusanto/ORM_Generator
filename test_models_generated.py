# test_models_generated.py
from database_manager import DatabaseManager
from models import Category, Product

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

print("=== TEST PENGGUNAAN MODEL DARI GENERATOR ===")

# 2. Buat data Category menggunakan Model yang digenerate otomatis
elektronik = Category.create(name="Elektronik")
fashion = Category.create(name="Fashion")

# 3. Buat data Product yang berelasi dengan Category
p1 = Product.create(category_id=elektronik.id, name="Smartphone Android", price=3500000)
p2 = Product.create(category_id=elektronik.id, name="Laptop Core i5", price=8500000)
p3 = Product.create(category_id=fashion.id, name="Kemeja Flanel", price=150000)

print("Kategori Elektronik:", elektronik)
print("Daftar Produk Elektronik (Lazy Load via relasi otomatis):", [p.name for p in elektronik.products])

print("\nCek relasi belongs_to dari Product ke Category:")
print(f"Produk '{p1.name}' masuk ke kategori:", p1.category.name)

print("\n[SUKSES] Modul orm_generator.py dan relasi otomatisnya berjalan tanpa cela!")