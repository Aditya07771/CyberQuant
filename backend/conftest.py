import sys
from pathlib import Path

# Add backend directory to sys.path so risk_engine and api are importable in tests
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
