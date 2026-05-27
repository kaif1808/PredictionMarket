release: alembic upgrade head
web: uvicorn server.server:combined_app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 75
