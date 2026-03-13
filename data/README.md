# Data Layout

- `prompts/`: benchmark task CSV files.
- `tests/`: evaluation code (`execute_test` modules).
- `structured_outputs/`: optional Pydantic schemas per prompt.
- `ifc/`: IFC assets used during benchmark runs.

## CSV Schema

All prompt CSV files use:

`question,test,ifc-file,structured-output,CRUD`

## Remote Data

If you host large IFC assets on Hugging Face, keep `data/manifest.json` updated and use:

```bash
python scripts/download_data.py --repo-id <org/repo>
```
