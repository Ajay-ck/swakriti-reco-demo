"""Start one backend worker on the hosting platform's assigned port."""
import os
from pathlib import Path
import sys
if __name__ == "__main__":
    backend = Path(__file__).resolve().parent / "backend"
    os.chdir(backend)
    sys.path.insert(0, str(backend))
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), workers=1)
