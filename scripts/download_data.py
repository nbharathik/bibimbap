"""Download benchmark data assets from Hugging Face datasets."""

import argparse
import hashlib
import json
import os
from pathlib import Path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_checksums(manifest_path: Path, data_root: Path) -> None:
    if not manifest_path.exists():
        print(f"Manifest not found, skipping checksum validation: {manifest_path}")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if not files:
        print("No checksums in manifest, skipping checksum validation.")
        return

    errors = []
    for item in files:
        rel_path = item.get("path")
        expected = item.get("sha256")
        if not rel_path or not expected:
            continue
        target = data_root / rel_path
        if not target.exists():
            errors.append(f"Missing file: {target}")
            continue
        actual = compute_sha256(target)
        if actual.lower() != str(expected).lower():
            errors.append(f"Checksum mismatch: {target}")

    if errors:
        joined = "\n".join(errors)
        raise SystemExit(f"Checksum validation failed:\n{joined}")
    print("Checksum validation passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download benchmark data from Hugging Face.")
    parser.add_argument(
        "--repo-id",
        default="your-org/bibimbap-data",
        help="Hugging Face dataset repo id.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Dataset revision/tag/commit to download.",
    )
    parser.add_argument(
        "--dest",
        default="data/ifc",
        help="Destination directory for downloaded IFC assets.",
    )
    parser.add_argument(
        "--manifest",
        default="data/manifest.json",
        help="Manifest file used for optional checksum validation.",
    )
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="Environment variable that stores Hugging Face token.",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        raise SystemExit(
            "huggingface-hub is required. Install dependencies from requirements.txt."
        ) from exc

    dest = Path(args.dest).resolve()
    manifest_path = Path(args.manifest).resolve()
    token = os.getenv(args.token_env)

    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading dataset '{args.repo_id}' to {dest} ...")

    snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
        local_dir=str(dest),
        token=token,
        local_dir_use_symlinks=False,
    )

    validate_checksums(manifest_path, dest.parent if dest.name == "ifc" else dest)


if __name__ == "__main__":
    main()
