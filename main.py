import os
import sys

# Add Backend directory to sys.path so its modules can be found
backend_path = os.path.join(os.path.dirname(__file__), "Backend")
sys.path.append(backend_path)

# Import the FastAPI app from Backend/main.py
from main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
