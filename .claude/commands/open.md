Start the DQAR web server if it is not already running, then open http://localhost:8000 in the browser.

Check whether uvicorn is already listening on port 8000 before starting a new instance. Use `lsof -ti:8000` to check. If nothing is running, start it with `.venv/bin/uvicorn web.app:app --reload --port 8000` in the background. Then run `open http://localhost:8000`.
