"""
Test script for HTML to PNG conversion
Run: python test_html_to_png.py
"""
import asyncio
import base64
from app.services.html_to_image import convert_html_to_png, initialize_converter, close_converter


async def test_simple_html():
    """Test 1: Simple gradient poster"""
    print("\n" + "="*60)
    print("TEST 1: Simple Gradient Poster")
    print("="*60)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 1080px;
                height: 1080px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: Arial, sans-serif;
            }
            .poster {
                color: white;
                font-size: 64px;
                font-weight: bold;
                text-align: center;
                text-shadow: 2px 2px 10px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>
        <div class="poster">
            HTML to PNG<br>
            ✨ Working! ✨
        </div>
    </body>
    </html>
    """

    try:
        data_url = await convert_html_to_png(
            html=html,
            dimensions={"width": 1080, "height": 1080},
            scale=1.0
        )

        # Save to file
        base64_data = data_url.split(",")[1]
        with open("test_simple.png", "wb") as f:
            f.write(base64.b64decode(base64_data))

        print("Success! Saved to test_simple.png")
        print(f"   Data URL length: {len(data_url)} chars")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False


async def test_complex_poster():
    """Test 2: Complex poster with Google Fonts"""
    print("\n" + "="*60)
    print("TEST 2: Complex Poster with Google Fonts")
    print("="*60)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;800&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 1080px;
                height: 1350px;
                background: linear-gradient(180deg, #0a0a0a 0%, #1a1a2e 100%);
                font-family: 'Poppins', sans-serif;
                padding: 60px;
                position: relative;
            }
            .title {
                color: #feca57;
                font-size: 72px;
                font-weight: 800;
                line-height: 1.2;
                margin-bottom: 30px;
            }
            .subtitle {
                color: #f0f0f0;
                font-size: 28px;
                font-weight: 600;
                margin-bottom: 50px;
            }
            .stats {
                display: flex;
                gap: 40px;
                margin-top: 60px;
            }
            .stat {
                background: rgba(254, 202, 87, 0.1);
                border: 2px solid #feca57;
                border-radius: 20px;
                padding: 30px;
                flex: 1;
            }
            .stat-number {
                color: #feca57;
                font-size: 56px;
                font-weight: 800;
                margin-bottom: 10px;
            }
            .stat-label {
                color: #f0f0f0;
                font-size: 20px;
                font-weight: 600;
            }
            .footer {
                position: absolute;
                bottom: 60px;
                left: 60px;
                color: #888;
                font-size: 18px;
            }
        </style>
    </head>
    <body>
        <div class="title">
            Power Your<br>
            Growth Journey
        </div>
        <div class="subtitle">
            Join 10,000+ creators building their audience
        </div>
        <div class="stats">
            <div class="stat">
                <div class="stat-number">487</div>
                <div class="stat-label">Sessions</div>
            </div>
            <div class="stat">
                <div class="stat-number">4.9★</div>
                <div class="stat-label">Rating</div>
            </div>
            <div class="stat">
                <div class="stat-number">98%</div>
                <div class="stat-label">Satisfaction</div>
            </div>
        </div>
        <div class="footer">
            @johndoe • Powered by Topmate
        </div>
    </body>
    </html>
    """

    try:
        data_url = await convert_html_to_png(
            html=html,
            dimensions={"width": 1080, "height": 1350},
            scale=1.0
        )

        # Save to file
        base64_data = data_url.split(",")[1]
        with open("test_complex.png", "wb") as f:
            f.write(base64.b64decode(base64_data))

        print("✅ Success! Saved to test_complex.png")
        print(f"   Data URL length: {len(data_url)} chars")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def test_csv_template():
    """Test 3: CSV template simulation"""
    print("\n" + "="*60)
    print("TEST 3: CSV Template with Placeholders")
    print("="*60)

    # Simulate CSV data
    csv_data = {
        "username": "johndoe",
        "name": "John Doe",
        "bookings": "487",
        "rating": "4.9"
    }

    # Template with placeholders
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 1080px;
                height: 1080px;
                background: #667eea;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                font-family: Arial, sans-serif;
                color: white;
            }
            .name {
                font-size: 64px;
                font-weight: bold;
                margin-bottom: 30px;
            }
            .stats {
                font-size: 32px;
                text-align: center;
                line-height: 1.8;
            }
        </style>
    </head>
    <body>
        <div class="name">{name}</div>
        <div class="stats">
            @{username}<br>
            ⭐ {rating}/5 Rating<br>
            📅 {bookings} Bookings
        </div>
    </body>
    </html>
    """

    # Replace placeholders
    filled_html = template
    for key, value in csv_data.items():
        filled_html = filled_html.replace(f"{{{key}}}", value)

    try:
        data_url = await convert_html_to_png(
            html=filled_html,
            dimensions={"width": 1080, "height": 1080},
            scale=1.0
        )

        # Save to file
        base64_data = data_url.split(",")[1]
        with open("test_csv.png", "wb") as f:
            f.write(base64.b64decode(base64_data))

        print("✅ Success! Saved to test_csv.png")
        print(f"   Data URL length: {len(data_url)} chars")
        print(f"   CSV data: {csv_data}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("HTML TO PNG CONVERSION TESTS")
    print("="*60)

    # Initialize Playwright
    print("\nInitializing Playwright browser...")
    await initialize_converter()
    print("Playwright initialized\n")

    # Run tests
    results = []
    results.append(await test_simple_html())
    results.append(await test_complex_poster())
    results.append(await test_csv_template())

    # Close Playwright
    print("\nClosing Playwright browser...")
    await close_converter()
    print("Playwright closed")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\nAll tests passed! HTML to PNG is working perfectly.")
        print("\nGenerated files:")
        print("  - test_simple.png")
        print("  - test_complex.png")
        print("  - test_csv.png")
    else:
        print("\nSome tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
