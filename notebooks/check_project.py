from pathlib import Path

root = Path(".")

required = [
    "data/raw",
    "data/processed",
    "data/db",
    "dashboard",
    "reports",
    "scripts",
    "sql",
    "notebooks",
    "bonus",
    "README.md",
    "requirements.txt"
]

print("=" * 50)
print("PROJECT STRUCTURE CHECK")
print("=" * 50)

for item in required:
    p = root / item
    if p.exists():
        print(f"✓ {item}")
    else:
        print(f"✗ Missing: {item}")