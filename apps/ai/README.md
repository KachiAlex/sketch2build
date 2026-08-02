# Sketch2Build AI Processing Service

Python / FastAPI service for:

- Computer vision sketch digitization
- Natural-language intent parsing (LLM)
- Geometry/layout generation
- Compliance checking helpers

## Local development

```bash
cd apps/ai
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```
