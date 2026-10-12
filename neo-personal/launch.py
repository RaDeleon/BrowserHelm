"""Isolated bundled Python entrypoint. Import only the adjacent engine modules."""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from browserhelm import main
main()
