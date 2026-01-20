"""
Custom server runner for Windows
"""
import uvicorn

if __name__ == "__main__":
    print("[SERVER] Starting server with html2image (Windows-compatible)...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
