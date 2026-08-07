# TreeTap Python Package

Python module for ingesting, processing, and managing TreeTap acoustic velocity signals and measurement session summaries in a unified DuckDB database backend.

Supports multiple hardware device generations:
- **v2**: File and zip archive ingestion (`treetap-*.csv` summary files & `000000XXXX.csv` tap signals in zip archives).
- **v1**: Serial communication acquisition interface.

## Usage

```bash
# Ingest data/v2 into DuckDB
python -m treetap v2 ingest data/v2 --db treetap.duckdb
```
