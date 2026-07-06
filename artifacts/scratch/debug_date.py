import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
from refineflow.config import DATE_FORMATS, DATE_PARSE_CONFIDENCE

s = pd.Series(["2025-05-12", "2025/05/13", "2025-05-14"])
non_null = s.dropna()
sample = non_null.sample(3, random_state=42).astype(str).str.strip()

print("Sample:")
print(sample)

# 1. Try to_datetime default
try:
    parsed_sample = pd.to_datetime(sample, errors="coerce")
    rate = parsed_sample.notna().mean()
    print("Default to_datetime parse rate:", rate)
    print(parsed_sample)
except Exception as e:
    print("Default parse raised:", e)

# 2. Try formats
for fmt in DATE_FORMATS:
    try:
        parsed_sample = pd.to_datetime(sample, format=fmt, errors="coerce")
        rate = parsed_sample.notna().mean()
        if rate > 0:
            print(f"Format {fmt} rate: {rate}")
            print(parsed_sample)
    except Exception as e:
        pass
