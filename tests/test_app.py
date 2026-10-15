from pathlib import Path
import sys

html_path = Path(__file__).resolve().parents[1] / "index.html"
html = html_path.read_text(encoding="utf-8").lower()

checks = {
    "page title": "<title>online food ordering portal</title>",
    "restaurant details": "spice route kitchen",
    "food categories": 'data-category="pizza"',
    "menu item": "classic margherita",
    "food price": "₹249",
    "availability status": "available now",
    "promotional offers": "welcome20",
    "thank-you feature": "thank you for ordering from spice route kitchen",
}

failed = []

for label, expected in checks.items():
    if expected in html:
        print("PASS - " + label)
    else:
        print("FAIL - " + label)
        failed.append(label)

if failed:
    print("Failed checks:", ", ".join(failed))
    sys.exit(1)

print("All", len(checks), "automated tests passed.")