-- 1. Tabel USERS (Kasir / Staff / Admin POS)
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, -- Untuk autentikasi login POS
    full_name TEXT NOT NULL,
    status TEXT DEFAULT 'active', -- 'active', 'inactive'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabel ROLES (Hak Akses)
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL, -- Contoh: 'admin', 'cashier', 'manager'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabel ROLE_USER (Relasi Many-to-Many User dengan Role)
CREATE TABLE role_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    UNIQUE(user_id, role_id)
);

-- 4. Tabel CUSTOMERS (Pelanggan Toko / Member)
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    company_name TEXT,
    phone_number TEXT UNIQUE, -- Kontak utama pelanggan di POS
    address TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Tabel SUPPLIERS (Pemasok Barang / Vendor)
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone_number TEXT,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Tabel ITEMS (Produk / Barang Inventaris Toko)
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL, -- Barcode / SKU produk
    name TEXT NOT NULL,
    category TEXT,
    unit TEXT NOT NULL, -- Satuan (pcs, pack, kg, botol, dll)
    buy_price NUMERIC DEFAULT 0, -- Harga modal / HPP
    sell_price NUMERIC DEFAULT 0, -- Harga jual ke konsumen
    stock INTEGER DEFAULT 0, -- Sisa stok real-time
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Tabel SALES (Header Transaksi Penjualan Kasir)
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT UNIQUE NOT NULL, -- Nomor Struk / Faktur
    customer_id INTEGER, -- Opsional (jika pembeli umum/non-member dikosongkan)
    user_id INTEGER, -- Kasir yang melayani transaksi
    subtotal_amount NUMERIC DEFAULT 0,
    discount_amount NUMERIC DEFAULT 0,
    total_amount NUMERIC DEFAULT 0, -- Total akhir setelah diskon
    payment_method TEXT DEFAULT 'cash', -- 'cash', 'qris', 'debit', 'transfer'
    payment_status TEXT DEFAULT 'paid', -- 'paid', 'pending', 'cancelled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 8. Tabel SALES_DETAILS (Item Barang dalam Struk Penjualan)
CREATE TABLE sale_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL, -- Harga jual saat transaksi
    subtotal NUMERIC NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE RESTRICT
);

-- 9. Tabel PURCHASES (Header Transaksi Pembelian / Restock Stok)
CREATE TABLE purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_no TEXT UNIQUE NOT NULL, -- Nomor referensi kulakan/po
    supplier_id INTEGER,
    user_id INTEGER, -- Staff yang menerima barang
    total_amount NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'received', -- 'ordered', 'received', 'cancelled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 10. Tabel PURCHASE_DETAILS (Detail Item Barang Masuk saat Restock)
CREATE TABLE purchase_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL, -- Harga kulakan satuan
    subtotal NUMERIC NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE RESTRICT
);