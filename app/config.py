from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "db"
RAW_DIR = DATA_DIR / "raw"
ASTRA_RAW_DIR = RAW_DIR / "astra"
UPLOADS_DIR = DATA_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"

TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

DB_PATH = DB_DIR / "certchecker.sqlite3"
ALIASES_PATH = CONFIG_DIR / "component_aliases.yml"


def ensure_directories() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ASTRA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)