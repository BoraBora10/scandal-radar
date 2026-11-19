import os
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    if not (Path(__file__).resolve().parents[1] / "dist/client/index.html").is_file():
        raise SystemExit(
            "Build the dashboard with 'npm ci' and 'npm run build', or download "
            "scandal-radar-local.zip from the project's GitHub releases."
        )
    load_dotenv()
    uvicorn.run("api.main:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
