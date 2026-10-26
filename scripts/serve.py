"""Single-process deployment entry point; honors the platform's assigned port."""
import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
                workers=1, proxy_headers=False, timeout_graceful_shutdown=15)
