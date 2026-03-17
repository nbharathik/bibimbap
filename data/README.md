## Download Data

The prompts and ifc files are hosted on Hugging Face. Download the data using: 

```bash
python scripts/download_data.py
```

## Data Layout

- `prompts/`: benchmark task CSV files. (Download from Hugging Face)
- `tests/`: evaluation code (`execute_test` modules).
- `structured_outputs/`: optional Pydantic schemas per prompt.
- `ifc/`: IFC assets used during benchmark runs. (Download from Hugging Face)

## CSV Schema

All prompt CSV files use:

`question,test,ifc-file,structured-output,CRUD`

