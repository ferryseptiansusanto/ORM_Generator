# demo_advanced.py
from database_manager import DatabaseManager
from eloquent_base import Model, relation


# ==========================================
# 1. SETUP MODEL & OBSERVER
# ==========================================

class UserObserver:
    def before_create(self, user: 'User'):
        print(f"[Observer] Membuat slug otomatis untuk {user.name}...")
        user.slug = user.name.lower().replace(" ", "-")

    def before_delete(self, user: 'User'):
        if user.name.lower() == "admin":
            print("[Observer] GAGAL: Akun Admin tidak boleh dihapus!")
            return False


class User(Model):
    table = "users"
    fillable = ["name", "slug"]


# Daftarkan Observer ke Model User
User.observe(UserObserver)


class Comment(Model):
    table = "comments"
    fillable = ["body", "commentable_id", "commentable_type"]

    @relation
    def commentable(self):
        # Relasi MorphTo (Bisa dimiliki oleh Post atau Video)
        return self.morph_to(morph_name="commentable")


class Post(Model):
    table = "posts"
    fillable = ["title"]

    @relation
    def comments(self):
        # Relasi MorphMany untuk komentar
        return self.morph_many(Comment, morph_name="commentable")


class Video(Model):
    table = "videos"
    fillable = ["title"]

    @relation
    def comments(self):
        # Relasi MorphMany untuk komentar
        return self.morph_many(Comment, morph_name="commentable")


# ==========================================
# 2. SETUP DATABASE SQLITE IN-MEMORY
# ==========================================
conn = DatabaseManager.get_connection("default")
conn.executescript("""
    DROP TABLE IF EXISTS users; 
    DROP TABLE IF EXISTS posts;
    DROP TABLE IF EXISTS videos;
    DROP TABLE IF EXISTS comments;

    CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT);
    CREATE TABLE posts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT);
    CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT);
    CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        body TEXT, 
        commentable_id INTEGER, 
        commentable_type TEXT
    );
""")
conn.commit()

# ==========================================
# 3. PENGUJIAN
# ==========================================
print("=== 1. TEST OBSERVER ===")
admin = User.create(name="Admin")
budi = User.create(name="Budi Santoso")
print(f"Hasil Slug Budi: {budi.slug}")
print(f"Hapus Admin Berhasil? {admin.delete()}")

print("\n=== 2. TEST POLYMORPHIC RELATIONS ===")
post1 = Post.create(title="Belajar Python ORM")
video1 = Video.create(title="Tutorial YouTube ORM")

# Menambahkan komentar ke Post
Comment.create(body="Komentar pertama pada Post", commentable_id=post1.id, commentable_type="Post")
# Menambahkan komentar ke Video
Comment.create(body="Videonya sangat bermanfaat!", commentable_id=video1.id, commentable_type="Video")

print(f"Komentar di Post '{post1.title}': {[c.body for c in post1.comments]}")
print(f"Komentar di Video '{video1.title}': {[c.body for c in video1.comments]}")

print("\n=== 3. TEST MORPH_TO (REVERSE) ===")
komen1 = Comment.find(1)
print(f"Induk dari Komentar 1: {komen1.commentable.__class__.__name__} -> {komen1.commentable.title}")

komen2 = Comment.find(2)
print(f"Induk dari Komentar 2: {komen2.commentable.__class__.__name__} -> {komen2.commentable.title}")