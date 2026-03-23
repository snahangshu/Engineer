import os
import sys
import importlib.util

# 1. Add Backend directory to path so relative imports inside it work
backend_dir = os.path.join(os.path.dirname(__file__), "Backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 2. Load the actual app from Backend/main.py using a unique module name
# to avoid "circular import" conflicts with THIS file (also called main.py)
backend_main_path = os.path.join(backend_dir, "main.py")
spec = importlib.util.spec_from_file_location("backend_main_context", backend_main_path)
backend_module = importlib.util.module_from_spec(spec)

# Add it to sys.modules so it behaves like a proper module
sys.modules["backend_main_context"] = backend_module
spec.loader.exec_module(backend_module)

# 3. Export the app so uvicorn main:app finds it
app = backend_module.app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
