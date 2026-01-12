import argparse
import csv
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv


@dataclass(frozen=True)
class VisionQuestion:
    qid: str
    category: str
    image_paths: List[str]
    question: str
    answer_type: str  # number | text | boolean | any
    expected: str
    system_prompt: str


class VisionModel:
    def generate(self, *, system_prompt: str, user_prompt: str, image_paths: List[Path]) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError


def model_suffix(model_name: str) -> str:
    # Keep filenames short and filesystem-friendly.
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_name.strip())
    return safe[-80:] if len(safe) > 80 else safe


def load_config(config_path: Path) -> dict:
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {config_path}. Create it or pass --config.")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in config file: {config_path}. {exc}")


def resolve_path(base_dir: Path, path_value: str) -> Path:
    p = Path(path_value)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def parse_image_paths(value: str) -> List[str]:
    if value is None:
        return []
    raw = str(value).strip()
    if not raw:
        return []
    # allow ; or | separated lists
    parts = [p.strip() for p in re.split(r"[;|]", raw) if p.strip()]
    return parts


def load_questions_csv(csv_path: Path) -> List[VisionQuestion]:
    questions: List[VisionQuestion] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "category", "image_paths", "question"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Questions CSV missing columns: {sorted(missing)}")

        for idx, row in enumerate(reader):
            qid = str(row.get("id") or idx).strip()
            category = str(row.get("category") or "").strip()
            question = str(row.get("question") or "").strip()
            image_paths = parse_image_paths(str(row.get("image_paths") or ""))

            if not question or not image_paths:
                continue

            answer_type = str(row.get("answer_type") or "any").strip().lower()
            expected = str(row.get("expected") or "").strip()
            system_prompt = str(row.get("system_prompt") or "").strip()

            questions.append(
                VisionQuestion(
                    qid=qid,
                    category=category,
                    image_paths=image_paths,
                    question=question,
                    answer_type=answer_type,
                    expected=expected,
                    system_prompt=system_prompt,
                )
            )
    return questions


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_first_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def parse_number(s: str) -> Optional[float]:
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def parse_bool(s: str) -> Optional[bool]:
    t = normalize_text(s)
    if t in {"yes", "true", "y", "1"}:
        return True
    if t in {"no", "false", "n", "0"}:
        return False
    return None


def score_prediction(expected: str, predicted: str, answer_type: str) -> Tuple[Optional[float], Dict[str, float]]:
    expected = (expected or "").strip()
    if not expected:
        return None, {}

    at = (answer_type or "any").lower()
    if at == "number":
        exp = parse_number(expected)
        got = parse_number(predicted)
        ok = (exp is not None) and (got is not None) and (exp == got)
        return (1.0 if ok else 0.0), {"exact_number": 1.0 if ok else 0.0}

    if at == "boolean":
        expb = parse_bool(expected)
        gotb = parse_bool(predicted)
        ok = (expb is not None) and (gotb is not None) and (expb == gotb)
        return (1.0 if ok else 0.0), {"exact_boolean": 1.0 if ok else 0.0}

    # default text compare
    ok = normalize_text(expected) == normalize_text(predicted)
    return (1.0 if ok else 0.0), {"exact_text": 1.0 if ok else 0.0}


def build_structured_prompt(question: VisionQuestion) -> Tuple[str, str]:
    system_prompt = question.system_prompt.strip() or "You are a visual question answering system."

    # Force a stable, machine-readable output.
    user_prompt = (
        f"Question: {question.question}\n"
        "\n"
        "Return ONLY valid JSON (no markdown, no extra text) with this schema:\n"
        "{\n"
        "  \"answer\": string,\n"
        "  \"answer_type\": \"number\" | \"boolean\" | \"text\" | \"unknown\",\n"
        "  \"confidence\": number,\n"
        "  \"notes\": string\n"
        "}\n"
        "\n"
        "Rules:\n"
        "- If you cannot determine the answer, set answer=\"unknown\" and answer_type=\"unknown\".\n"
        "- For number answers, the 'answer' must contain just the number (e.g. \"4\").\n"
        "- For boolean answers, the 'answer' must be \"yes\" or \"no\".\n"
    )

    return system_prompt, user_prompt


class DummyVisionModel(VisionModel):
    """Deterministic model for local testing (no network)."""

    def generate(self, *, system_prompt: str, user_prompt: str, image_paths: List[Path]) -> Tuple[str, Dict[str, Any]]:
        # Extremely simple: if question contains a number in expected format, echo 1.
        payload = {
            "answer": "unknown",
            "answer_type": "unknown",
            "confidence": 0.0,
            "notes": "dummy",
        }
        if "how many" in user_prompt.lower():
            payload.update({"answer": "1", "answer_type": "number", "confidence": 0.5})
        if "is there" in user_prompt.lower():
            payload.update({"answer": "yes", "answer_type": "boolean", "confidence": 0.5})
        return json.dumps(payload), {"input_tokens": 0, "output_tokens": 0}


class GeminiVisionModel(VisionModel):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise SystemExit("Missing GEMINI_API_KEY (or GOOGLE_API_KEY) in environment.")

        try:
            import google.generativeai as genai  # type: ignore
        except Exception as exc:
            raise SystemExit(
                "Gemini provider requires package 'google-generativeai'. "
                "Install it via: pip install google-generativeai pillow\n"
                f"Import error: {exc}"
            )

        genai.configure(api_key=self.api_key)
        self._genai = genai

    def generate(self, *, system_prompt: str, user_prompt: str, image_paths: List[Path]) -> Tuple[str, Dict[str, Any]]:
        try:
            from PIL import Image  # type: ignore
        except Exception as exc:
            raise SystemExit(
                "Gemini provider requires package 'pillow'. Install via: pip install pillow\n"
                f"Import error: {exc}"
            )

        model = self._genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
        )

        parts: List[Any] = [user_prompt]
        for p in image_paths:
            parts.append(Image.open(p))

        resp = model.generate_content(parts)
        text = getattr(resp, "text", None) or ""

        # Usage metadata is best-effort.
        usage = getattr(resp, "usage_metadata", None)
        meta: Dict[str, Any] = {}
        if usage is not None:
            meta["input_tokens"] = int(getattr(usage, "prompt_token_count", 0) or 0)
            meta["output_tokens"] = int(getattr(usage, "candidates_token_count", 0) or 0)
        return text, meta


def build_provider(provider: str, model_name: str) -> VisionModel:
    p = (provider or "").strip().lower()
    if p == "dummy":
        return DummyVisionModel()
    if p == "gemini":
        return GeminiVisionModel(model_name=model_name)
    raise SystemExit(f"Unknown provider: {provider}. Supported: gemini, dummy")


def main() -> None:
    default_config = Path(__file__).resolve().parent / "configs" / "image_benchmark.config.example.json"

    parser = argparse.ArgumentParser(description="Run an image / vision benchmark (no MCP server involved).")
    parser.add_argument("--config", default=str(default_config), help="Path to the image benchmark config JSON file.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)

    base_dir = repo_root
    config_dir = config_path.parent

    env_path = config_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    questions_path = resolve_path(base_dir, config["questions_csv"])
    questions = load_questions_csv(questions_path)
    if not questions:
        raise SystemExit(f"No questions loaded from {questions_path}")

    num_samples = int(config.get("num_samples", 1))
    provider_name = str(config.get("provider", "gemini"))
    model_name = str(config.get("model_name", "gemini-2.0-flash"))
    default_system_prompt = str(config.get("system_prompt", "")).strip()

    paths_config = config.get("paths", {})
    results_dir = resolve_path(base_dir, paths_config.get("results_dir", "results"))
    results_dir.mkdir(parents=True, exist_ok=True)

    # Run directory
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = results_dir / f"run_{run_timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Result for this run will be stored in: {run_dir}")

    with (run_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    results_config = config.get("results", {})
    cache_filename = str(results_config.get("cache_filename_template", "cache_{model_suffix}.json")).format(
        model_suffix=model_suffix(model_name)
    )
    cache_path = run_dir / cache_filename

    cache: Dict[str, Any] = {}
    cache_source = config.get("cache_source")
    if cache_source:
        cache_source_path = resolve_path(base_dir, cache_source)
        if cache_source_path.exists():
            try:
                with cache_source_path.open("r", encoding="utf-8") as cache_file:
                    cache = json.load(cache_file)
                print(f"Loaded existing cache from: {cache_source_path}")
            except Exception as exc:
                print(f"Warning: Failed to load cache source {cache_source_path}: {exc}")

    model = build_provider(provider_name, model_name)

    # Execute questions
    for idx, q in enumerate(questions):
        print(f"Processing question {idx + 1} of {len(questions)} (id={q.qid})...")
        if str(q.qid) in cache:
            print("Question already in cache. Using cached result.")
            continue

        img_paths: List[Path] = []
        for p in q.image_paths:
            resolved = resolve_path(base_dir, p)
            if not resolved.exists():
                raise SystemExit(f"Image not found: {p} -> {resolved}")
            img_paths.append(resolved)

        sys_prompt, user_prompt = build_structured_prompt(
            VisionQuestion(
                qid=q.qid,
                category=q.category,
                image_paths=q.image_paths,
                question=q.question,
                answer_type=q.answer_type,
                expected=q.expected,
                system_prompt=q.system_prompt or default_system_prompt,
            )
        )

        sample_results = []
        for sample in range(num_samples):
            try:
                raw_text, usage = model.generate(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    image_paths=img_paths,
                )
            except Exception as exc:
                sample_results.append(
                    {
                        "sample": sample + 1,
                        "model_output": {
                            "raw": "",
                            "parsed": {},
                            "predicted": "",
                            "expected": q.expected,
                            "answer_type": q.answer_type,
                            "scored": False,
                            "error": str(exc),
                        },
                        "tool_call_iterations": [],
                        "metrics": {},
                        "score": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "error": str(exc),
                    }
                )
                continue

            parsed = extract_first_json_object(raw_text) or {}
            predicted = str(parsed.get("answer") or "").strip() or str(raw_text).strip()

            score, metrics = score_prediction(q.expected, predicted, q.answer_type)
            # Keep analyze_results.py compatible: always write numeric score.
            if score is None:
                score_value = 0
                metrics_value: Dict[str, float] = {}
                scored = False
            else:
                score_value = float(score)
                metrics_value = metrics
                scored = True

            sample_results.append(
                {
                    "sample": sample + 1,
                    "model_output": {
                        "raw": raw_text,
                        "parsed": parsed,
                        "predicted": predicted,
                        "expected": q.expected,
                        "answer_type": q.answer_type,
                        "scored": scored,
                    },
                    "tool_call_iterations": [],
                    "metrics": metrics_value,
                    "score": score_value,
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                }
            )

        cache[str(q.qid)] = {
            "question_id": q.qid,
            "prompt": q.question,
            "model": model_name,
            "category": q.category,
            "images": q.image_paths,
            "results": sample_results,
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }

        with cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)

    # Write a simple summary.csv focused on scored questions.
    summary_rows: List[Dict[str, Any]] = []
    scored_scores: List[float] = []
    for qid, qdata in cache.items():
        for r in qdata.get("results", []):
            mo = r.get("model_output")
            if isinstance(mo, dict):
                scored = bool(mo.get("scored"))
            else:
                scored = False
            score = float(r.get("score", 0) or 0)
            if scored:
                scored_scores.append(score)
            summary_rows.append(
                {
                    "Question ID": qid,
                    "Category": qdata.get("category", ""),
                    "Prompt": (qdata.get("prompt", "") or "")[:200],
                    "Images": ";".join(qdata.get("images", []) or []),
                    "Sample": r.get("sample"),
                    "Scored": scored,
                    "Score": score,
                    "Input Tokens": r.get("input_tokens", 0),
                    "Output Tokens": r.get("output_tokens", 0),
                }
            )

    summary_path = run_dir / "summary.csv"
    try:
        import pandas as pd  # type: ignore

        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    except Exception:
        # pandas is already in requirements, but keep a fallback.
        with summary_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()) if summary_rows else [])
            writer.writeheader()
            writer.writerows(summary_rows)

    if scored_scores:
        avg = sum(scored_scores) / len(scored_scores)
        print(f"Scored samples: {len(scored_scores)}")
        print(f"Average scored score: {avg:.3f}")
    else:
        print("No rows had an 'expected' answer; nothing was scored.")

    print(f"Cache written to: {cache_path}")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()
