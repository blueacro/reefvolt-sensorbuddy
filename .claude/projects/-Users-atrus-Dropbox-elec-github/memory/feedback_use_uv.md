---
name: Use uv for Python
description: Always use uv (not pip) for Python package management and running Python scripts
type: feedback
---

Use `uv` for all Python operations — never use bare `pip install` or `pip`.

**Why:** User preference; uv is the standard Python tooling in this workspace.

**How to apply:** Use `uv pip install`, `uv run`, `uv add`, etc. for any Python package management or script execution across all projects.
