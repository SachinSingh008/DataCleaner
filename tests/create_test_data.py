"""
Generate sample CSV files for testing RefineFlow Module 1.
Run this once to create test data.
"""

import os
import csv
import random
import string

os.makedirs("tests/data", exist_ok=True)

# ── 1. Normal CSV ─────────────────────────────────────────────────────────────
rows = [["customer_id", "name", "age", "city", "revenue($)", "email", "  status "]]
cities = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"]
for i in range(500):
    rows.append([
        f"C{i:04d}", f"Customer {i}", random.randint(18, 80),
        random.choice(cities), round(random.uniform(1000, 50000), 2),
        f"cust{i}@example.com", random.choice(["Active", "Inactive", "active", "ACTIVE"])
    ])
# Add some nulls
for i in [10, 20, 30, 40, 50]:
    rows[i][2] = ""   # null age
    rows[i][4] = ""   # null revenue

with open("tests/data/normal.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)

# ── 2. CSV with issues ────────────────────────────────────────────────────────
rows2 = [["Customer Name", "Age", "Revenue ($)", "email address", "Age"]]  # duplicate col, spaces, symbols
for i in range(200):
    rows2.append([
        f"Name {i}", random.randint(18, 80),
        f"${random.uniform(1000, 50000):.2f}",
        f"user{i}@mail.com",
        random.randint(18, 80)   # duplicate age col
    ])

with open("tests/data/issues.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows2)

# ── 3. Nearly-all-null column ─────────────────────────────────────────────────
rows3 = [["id", "name", "corrupted_col", "single_val"]]
for i in range(300):
    rows3.append([
        i, f"Name {i}",
        "" if random.random() < 0.95 else "rare",   # 95% null → corrupted
        "CONSTANT"   # all same value → corrupted
    ])

with open("tests/data/corrupted.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows3)

# ── 4. High-duplicate CSV ─────────────────────────────────────────────────────
rows4 = [["order_id", "product", "qty"]]
base_rows = [["O001", "Widget", 5], ["O002", "Gadget", 3], ["O003", "Tool", 10]]
for i in range(300):
    rows4.append(random.choice(base_rows))   # ~100% duplicate rate

with open("tests/data/duplicates.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows4)

# ── 5. Empty file ──────────────────────────────────────────────────────────────
with open("tests/data/empty.csv", "w") as f:
    f.write("id,name,value\n")   # header only, no rows

# ── 6. Tiny file (< 10 rows) ──────────────────────────────────────────────────
with open("tests/data/tiny.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "value"])
    for i in range(5):
        w.writerow([i, i * 10])

print("[OK] Test data created in tests/data/")
print("  normal.csv     — 500 rows, mixed types")
print("  issues.csv     — col name problems (spaces, symbols, duplicates)")
print("  corrupted.csv  — 95% null col + all-same-value col")
print("  duplicates.csv — ~100% duplicate rows")
print("  empty.csv      — header only")
print("  tiny.csv       — 5 rows")
