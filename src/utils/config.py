from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_DIR / "data" / "processed"
RAW_DATA_PATH = PROJECT_DIR / "data" / "raw"
REFERENCE_DATA_PATH = PROJECT_DIR / "data" / "reference" / "reference_dataset.csv"
CURRENT_DATA_PATH = PROJECT_DIR / "data" / "current" / "current_dataset.csv"
MODELS_PATH = PROJECT_DIR / "models"
REPORTS_PATH = PROJECT_DIR / "reports"
DRIFT_REPORTS_PATH = REPORTS_PATH / "drift"
