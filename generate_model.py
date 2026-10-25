# File: orm/generate_model.py
import os
import sys
import logging
from pathlib import Path

# Configure logging according to production standards
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

CURRENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Dynamically resolve the submodule directory name to keep it safe from renaming
SUBMODULE_NAME: str = os.path.basename(CURRENT_DIR)

# Load database configurations
try:
    import database_config as project_db_config
except ImportError as e:
    logging.error("Failed to import database_config.py from the submodule path.")
    sys.exit(1)

from orm_generator import ORMGenerator


def get_default_database_path(databases: dict, config_path: str) -> str:
    """
    Resolve and return the absolute path for the default SQLite database connection.
    """
    if "default" not in databases:
        logging.error("Connection 'default' was not found in DATABASES configuration.")
        sys.exit(1)

    default_config: dict = databases["default"]
    if not isinstance(default_config, dict):
        logging.error("The 'default' database configuration must be a dictionary.")
        sys.exit(1)

    db_path: Optional[str] = default_config.get("database")
    if not db_path:
        logging.error("The 'database' key is missing or empty in 'default' connection.")
        sys.exit(1)

    # Expand any existing environment variables or user home structures
    db_path = os.path.expanduser(os.path.expandvars(str(db_path)))

    db_path_obj: Path = Path(db_path)
    if not db_path_obj.is_absolute():
        config_dir: Path = Path(os.path.dirname(os.path.abspath(config_path)))
        db_path_obj = config_dir / db_path_obj

    return str(db_path_obj)


def get_default_model_path(model_paths: dict, config_path: str) -> str:
    """
    Resolve and return the absolute target directory where models.py will be generated.
    """
    if not model_paths:
        logging.error("MODEL_PATH configuration is missing from database_config.")
        sys.exit(1)

    if "default" not in model_paths:
        logging.error("Connection 'default' was not found in MODEL_PATH layout.")
        sys.exit(1)

    default_model: Any = model_paths["default"]

    if isinstance(default_model, dict):
        model_path: Optional[str] = default_model.get("path") or default_model.get("model")
    elif isinstance(default_model, str):
        model_path = default_model
    else:
        logging.error("The value of MODEL_PATH['default'] must be a string or a dictionary.")
        sys.exit(1)

    if not model_path:
        logging.error("Model path string cannot be empty on MODEL_PATH['default'].")
        sys.exit(1)

    model_path = os.path.expanduser(os.path.expandvars(str(model_path)))

    model_path_obj: Path = Path(model_path)
    if not model_path_obj.is_absolute():
        config_dir: Path = Path(os.path.dirname(os.path.abspath(config_path)))
        model_path_obj = config_dir / model_path_obj

    return str(model_path_obj)


def main() -> None:
    """
    Main entry point for execution of the automated ORM code generator.
    """
    config_module: Any = project_db_config
    databases: dict = getattr(config_module, "DATABASES", {})
    model_paths: dict = getattr(config_module, "MODEL_PATH", {})

    config_path: str = os.path.abspath(
        getattr(config_module, "__file__", os.path.join(CURRENT_DIR, "database_config.py"))
    )

    abs_db_path: str = get_default_database_path(databases, config_path)

    if not Path(abs_db_path).is_file():
        logging.error(f"Database target file not found: {abs_db_path}")
        logging.error("Please run the migration framework script first.")
        sys.exit(1)

    model_dir: str = get_default_model_path(model_paths, config_path)
    os.makedirs(model_dir, exist_ok=True)
    output_file: str = os.path.join(model_dir, "models.py")

    logging.info(f"Loading environment settings from: {config_path}")
    logging.info(f"Target relational database: {abs_db_path}")
    logging.info(f"Target generator output path: {output_file}")
    logging.info(f"Detected sub-module folder namespace: {SUBMODULE_NAME}")
    logging.info("Initializing enterprise ORM reverse-engineering system...")

    # Inject the detected submodule name dynamically into the generator
    generator: ORMGenerator = ORMGenerator(
        connection_name="default",
        output_filename=output_file,
        submodule_name=SUBMODULE_NAME
    )

    generator.generate(include_pivot_models=False)

    if Path(output_file).is_file():
        logging.info(f"SUCCESS: The file models.py has been built at '{output_file}'.")
    else:
        logging.error(f"FAILED: Output model generation crashed at: {output_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
