from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.test_11 import execute_test


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "basic_tasks.ifc"
    edited_ifc_file = data_dir / "solutions" / "test_11.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
