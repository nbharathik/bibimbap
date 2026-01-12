import sys
from pathlib import Path

# Ensure repo root is importable when running this file directly.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from image_benchmark import (
    extract_first_json_object,
    parse_image_paths,
    score_prediction,
)


def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def run_tests() -> None:
    # image path parsing
    paths = parse_image_paths("data/images/BasicHouse_1.png; data/images/BasicHouse_2.png")
    _assert(len(paths) == 2, "Expected two image paths")

    # json extraction (plain)
    obj = extract_first_json_object('{"answer":"4","answer_type":"number","confidence":0.9,"notes":""}')
    _assert(obj is not None and obj.get("answer") == "4", "Expected JSON to parse")

    # json extraction (embedded)
    text = "some text before {\"answer\":\"yes\",\"answer_type\":\"boolean\",\"confidence\":0.7,\"notes\":\"\"} trailing"
    obj2 = extract_first_json_object(text)
    _assert(obj2 is not None and obj2.get("answer") == "yes", "Expected embedded JSON to be extracted")

    # scoring
    score, metrics = score_prediction("4", "4", "number")
    _assert(score == 1.0 and metrics.get("exact_number") == 1.0, "Expected exact number match")

    score2, metrics2 = score_prediction("yes", "no", "boolean")
    _assert(score2 == 0.0 and metrics2.get("exact_boolean") == 0.0, "Expected boolean mismatch")

    score3, metrics3 = score_prediction("Red", "red", "text")
    _assert(score3 == 1.0 and metrics3.get("exact_text") == 1.0, "Expected case-insensitive text match")


if __name__ == "__main__":
    run_tests()
    print("test_image_benchmark.py: OK")
