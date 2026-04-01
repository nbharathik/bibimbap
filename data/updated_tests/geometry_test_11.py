from pathlib import Path

try:
    from data.tests import geometry_test_11 as original_test
    from data.updated_tests._integrity_utils import run_integrity_check
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from data.tests import geometry_test_11 as original_test
    from data.updated_tests._integrity_utils import run_integrity_check


TARGET_GUIDS = [
    "3PQZwOmmD1hgPWgX4XFLJO",
    "3PQZwOmmD1hgPWgX4XFLJP",
    "3PQZwOmmD1hgPWgX4XFLJQ",
    "3PQZwOmmD1hgPWgX4XFLJR",
    "3PQZwOmmD1hgPWgX4XFLJV",
    "3PQZwOmmD1hgPWgX4XFLJU",
]


def execute_test(ifc_file, edited_ifc_file, model_output):
    metrics = dict(original_test.execute_test(ifc_file, edited_ifc_file, model_output))
    metrics["integrity_constraint"] = run_integrity_check(
        ifc_file,
        edited_ifc_file,
        target_guids=TARGET_GUIDS,
    )
    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "01" / "01_01_011.ifc"
    edited = data_dir / "solutions" / "geometry_11.ifc"
    print(execute_test(str(ifc_file), str(edited), None))
