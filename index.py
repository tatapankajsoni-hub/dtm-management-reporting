"""TATA_DTM Render entrypoint.

This file is intentionally thin: the application implementation lives in
main.py and is imported here so Render can use either `uvicorn main:app` or
`uvicorn index:app` without duplicating application code.
"""
from main import app

__all__ = ["app"]
