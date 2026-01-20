# Playwright Setup Guide

## What is Playwright?

Playwright is a browser automation library that runs headless Chromium to convert HTML to images. It's the Python equivalent of Puppeteer.

## Installation Steps

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs `playwright==1.40.0`

### 2. Install Playwright Browsers

**IMPORTANT:** You must install the browser binaries after installing the package:

```bash
# Windows
python -m playwright install chromium

# Or install all browsers (chromium, firefox, webkit)
python -m playwright install

# Linux/Mac
python3 -m playwright install chromium
```

This downloads the Chromium browser (~200MB) needed for HTML rendering.

### 3. Verify Installation

```bash
# Check if playwright is installed
python -m playwright --version

# Should output: Version 1.40.0 (or similar)
```

### 4. Test HTML to PNG

Create a test script:

```python
# test_html_to_png.py
import asyncio
from app.services.html_to_image import convert_html_to_png

async def test():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                margin: 0;
                padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                font-family: Arial, sans-serif;
            }
            .poster {
                color: white;
                font-size: 48px;
                font-weight: bold;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="poster">
            Hello from Playwright!<br>
            HTML → PNG ✨
        </div>
    </body>
    </html>
    """

    print("Converting HTML to PNG...")
    data_url = await convert_html_to_png(
        html=html,
        dimensions={"width": 1080, "height": 1080}
    )

    print(f"✅ Success! Data URL length: {len(data_url)}")
    print(f"First 100 chars: {data_url[:100]}...")

    # Save to file
    import base64
    base64_data = data_url.split(",")[1]
    with open("test_output.png", "wb") as f:
        f.write(base64.b64decode(base64_data))
    print("✅ Saved to test_output.png")

asyncio.run(test())
```

Run it:
```bash
cd backend
python test_html_to_png.py
```

You should see `test_output.png` created with the rendered HTML.

## Troubleshooting

### Error: "Executable doesn't exist"

**Problem:** Browser binaries not installed

**Solution:**
```bash
python -m playwright install chromium
```

### Error: "Browser closed unexpectedly"

**Problem:** Missing system dependencies (Linux)

**Solution (Ubuntu/Debian):**
```bash
sudo apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2
```

**Solution (CentOS/RHEL):**
```bash
sudo yum install -y \
    nss \
    nspr \
    atk \
    at-spi2-atk \
    cups-libs \
    libdrm \
    libxkbcommon \
    libXcomposite \
    libXdamage \
    libXfixes \
    libXrandr \
    mesa-libgbm \
    alsa-lib
```

### Error: "Cannot find module 'playwright'"

**Problem:** Wrong Python environment

**Solution:**
```bash
# Activate virtual environment first
cd backend
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Then install
pip install playwright
python -m playwright install chromium
```

### Performance Issues

**Problem:** Slow HTML to PNG conversion

**Solutions:**
1. Reduce scale factor (use 1.0 instead of 2.0)
2. Use shared browser instance (already implemented)
3. Process in smaller batches

## Docker Deployment

If deploying with Docker, add to Dockerfile:

```dockerfile
FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install chromium

# Copy application
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## How It Works

```python
# Backend starts up
uvicorn app.main:app --reload

# Lifespan event triggered
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Launch Chromium browser (kept alive)
    await initialize_converter()
    # Browser instance stays open for all requests

    yield

    # Shutdown: Close browser
    await close_converter()

# When request comes in:
# 1. Reuse existing browser instance
# 2. Create new page
# 3. Set HTML content
# 4. Take screenshot
# 5. Close page (browser stays alive)
# 6. Return PNG as data URL
```

## Benefits

✅ **Accurate Rendering** - Uses real Chromium browser
✅ **Fast** - Shared browser instance across requests
✅ **Fonts & CSS** - Supports Google Fonts, modern CSS
✅ **Images** - Can load external images
✅ **Async** - Non-blocking operations

## Memory Usage

- First launch: ~100-150MB (browser startup)
- Per conversion: ~10-20MB (page creation)
- Browser stays alive between requests

To reduce memory in production:
- Use smaller scale factor (1.0 instead of 2.0)
- Implement timeout for idle browser shutdown
- Use browser pooling for high traffic

## Next Steps

1. ✅ Install Playwright
2. ✅ Test conversion
3. Run backend with Playwright enabled
4. Test full bulk generation flow

Your HTML to PNG conversion is now ready! 🎉
