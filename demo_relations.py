# demo_relations.py
from database_manager import DatabaseManager
from eloquent_base import Model, relation

# 1. Definisi Model dengan Relasi
class User(Model):
    table = "users"
    fillable = ["name"]

    @relation
    def posts(self):
        # User memiliki banyak Post (foreign_key otomatis: 'user_id')
        return self.has_many(Post, foreign_key="user_id")


class Post(Model):
    table = "posts"
    fillable = ["user_id", "title", "status"]

    @relation
    def user(self):
        # Post dimiliki oleh satu User (foreign_key otomatis: 'user_id')
        return self.belongs_to(User, foreign_key="user_id")

    @relation
    def comments(self):
        return self.has_many(Comment, foreign_key="post_id")


class Comment(Model):
    table = "comments"
    fillable = ["post_id", "body"]

    @relation
    def post(self):
        return self.belongs_to(Post, foreign_key="post_id")


# 2. Setup Tabel di SQLite In-Memory
conn = DatabaseManager.get_connection("default")
conn.executescript("""
    CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
    CREATE TABLE posts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, status TEXT);
    CREATE TABLE comments (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, body TEXT);
""")
conn.commit()

# 3. Seed Data menggunakan .create()
u1 = User.create(name="Andi")
u2 = User.create(name="Budi")

p1 = Post.create(user_id=u1.id, title="Belajar Python ORM", status="published")
p2 = Post.create(user_id=u1.id, title="Draft Rahasia Andi", status="draft")
p3 = Post.create(user_id=u2.id, title="Tips SQLite Cepat", status="published")

Comment.create(post_id=p1.id, body="Artikel yang sangat bagus!")
Comment.create(post_id=p1.id, body="Ditunggu bagian selanjutnya.")
Comment.create(post_id=p3.id, body="Mantap Bang Budi!")

print("=== 1. TEST LAZY LOADING (has_many & belongs_to) ===")
andi = User.find(1)
# Diakses langsung sebagai properti (Lazy Load otomatis mengeksekusi query saat dibutuhkan)
print(f"Post milik {andi.name}:", [p.title for p in andi.posts])

post_pertama = Post.find(1)
# Akses belongs_to sebagai properti
print(f"Penulis '{post_pertama.title}' adalah:", post_pertama.user.name)

print("\n=== 2. TEST RELATION QUERY CHAINING ===")
# Memanggil relasi sebagai method () untuk menambahkan filter .where()
published_posts = andi.posts().where("status", "published").get()
print(f"Post {andi.name} yang sudah published:", [p.title for p in published_posts])

print("\n=== 3. TEST EAGER LOADING (.with_relations()) & NESTED RELATIONS ===")
# Memuat seluruh User sekaligus beserta Posts dan Comments di dalam Posts (Bebas N+1 Problem!)
users_with_data = User.with_relations("posts.comments").get()

for user in users_with_data:
    print(f"\nUser: {user.name}")
    for post in user.posts:
        print(f"  -> Post: {post.title} ({len(post.comments)} komentar)")
        for comment in post.comments:
            print(f"       * Komentar: {comment.body}")

print("\n=== 4. TEST SERIALISASI .to_dict() BESERTA RELASI ===")
print(users_with_data[0].to_dict())