# File ini di-generate secara otomatis oleh orm_generator.py

# Jangan diubah secara manual kecuali diperlukan.

from eloquent_base import Model, relation



class Category(Model):
    table = "categories"
    primary_key = "id"
    fillable = ['name']
    timestamps = True

    @relation
    def products(self):
        return self.has_many(Product, foreign_key="category_id")


class Product(Model):
    table = "products"
    primary_key = "id"
    fillable = ['category_id', 'name', 'price']
    timestamps = True
    soft_deletes = True
