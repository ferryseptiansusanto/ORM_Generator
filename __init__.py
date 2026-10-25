# orm/__init__.py
# Expose the public API for clean external imports

from .database_manager import DatabaseManager
from .eloquent_base import Model, relation

__all__ = ["DatabaseManager", "Model", "relation"]
