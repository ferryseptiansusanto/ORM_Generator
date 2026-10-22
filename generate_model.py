# main.py
from orm_generator import ORMGenerator

if __name__ == "__main__":
    # Inisialisasi generator dengan koneksi yang ingin dibaca (default: sqlite 'app.db')
    # Anda juga bisa menggunakan koneksi lain yang ada di database_config.py, misal: connection_name="pg_connection"
    generator = ORMGenerator(
        connection_name="default",
        output_filename="models.py"
    )

    # Jalankan proses generate
    # include_pivot_models=False berarti tabel pivot (many-to-many) otomatis
    # diubah menjadi relasi belongs_to_many pada model induknya.
    generator.generate(include_pivot_models=False)

    print("Selesai! File models.py berhasil dibuat.")