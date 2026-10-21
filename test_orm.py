# test_orm.py
from models import User, Post, Role,Transaction





# Masukkan data dummy
user = User.create(username="ferry_dev", email="ferry@example.com")
print("User dibuat:", user)

# Buat relasi Post
Post.create(user_id=user.id, title="Belajar ORM Python", body="Sangat mirip Laravel Eloquent!")

# Ambil data beserta relasinya
fetched_user = User.find(user.id)
print("Username:", fetched_user.username)


# Mengambil semua user beserta relasi posts-nya sekaligus
users = User.with_("posts").get()

for user in users:
    print(f"User: {user.username}")
    # Tidak ada query tambahan ke database saat mengakses .posts karena sudah di-load di awal!
    for post in user.posts:
        print(f" - Post: {post.title}")

# Mencari user aktif, diurutkan secara descending, beserta posts-nya yang dibatasi limit
active_users = (User.query()
                .where("email", "LIKE", "%@example.com")
                .order_by("created_at", "DESC")
                .with_("posts")
                .limit(5)
                .get())
for user in active_users:
    print(f"User: {user.username}")


user = User.find(1)
role_id = 2

# Menambahkan relasi pivot (attach)
user.roles.attach(role_id)

# Menghapus relasi pivot (detach)
user.roles.detach(role_id)

# Menyinkronkan daftar ID role secara otomatis (menambah yang baru, menghapus yang tidak ada di list)
user.roles.sync([1, 2, 3])


# Contoh: Menampilkan riwayat penimbangan halaman ke-1, dengan 20 data per halaman
page_number = 1
per_page_limit = 20

result = user.query().order_by("created_at", "DESC").paginate(per_page=per_page_limit, page=page_number)

# Mengakses data untuk dimasukkan ke QTableWidget PyQt5
users = result["data"]

print(f"Menampilkan halaman {result['current_page']} dari {result['last_page']} (Total Data: {result['total']})")

for tx in users:
    print(f"Username: {tx.username} - Email: {tx.email}")



def search_transactions(keyword_plat: str, tanggal_mulai: str, tanggal_selesai: str, page: int = 1):
    # Mulai bangun query dasar
    query = Transaction.query()

    # 1. Filter berdasarkan Nomor Plat (jika diisi oleh operator)
    if keyword_plat:
        # Menggunakan operator LIKE untuk pencarian parsial (mengandung kata kunci)
        query.where("plate_number", "LIKE", f"%{keyword_plat}%")

        # Atau jika Anda menggunakan helper 'search':
        # query.search("plate_number", keyword_plat)

    # 2. Filter berdasarkan Rentang Tanggal (jika diisi)
    if tanggal_mulai and tanggal_selesai:
        query.where("created_at", ">=", f"{tanggal_mulai} 00:00:00") \
            .where("created_at", "<=", f"{tanggal_selesai} 23:59:59")

    # 3. Urutkan dari yang terbaru dan terapkan pagination (misal 15 data per halaman)
    result = query.order_by("created_at", "DESC").paginate(per_page=15, page=page)

    return result


from database_manager import DB
from models import User, Post, Role

# =========================================================
# GAYA 1: Otomatis dengan Context Manager (Rekomendasi)
# =========================================================
try:
    with DB.transaction():
        # 1. Buat user baru
        user = User.create(username="ferry_dev", email="ferry@example.com")

        # 2. Buat post milik user
        Post.create(user_id=user.id, title="Transaksi Pertama", body="Isi artikel")

        # 3. Simulasi error di tengah jalan (misal gagal validasi bisnis)
        raise RuntimeError("Koneksi payment gateway terputus!")

except RuntimeError as err:
    print(f"Transaksi dibatalkan: {err}")
    # Data 'ferry_dev' dan 'Transaksi Pertama' TIDAK AKAN tersimpan di database (Otomatis Rollback!)

# =========================================================
# GAYA 2: Manual (begin_transaction, commit, rollback)
# =========================================================
DB.begin_transaction()
try:
    tx = Transaction.create(ticket_code="TCK-001", plate_number="B 1234 XYZ", net_weight=1500.5)
    DB.commit()
except Exception:
    DB.rollback()