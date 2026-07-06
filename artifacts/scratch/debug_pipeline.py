import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
from refineflow.cleaning.pipeline import CleaningPipeline

df = pd.DataFrame({
    "order_id": [101, 102, 102, 103],
    "user_email": ["a@b.com", "xyz.com", "b@c.com", "c@d.com"],
    "price": ["$10.00", "$20.00", "$20.00", "₹30.00"],
    "weight": ["1kg", "2kg", "2kg", "3kg"]
})

print("Raw df:")
print(df.dtypes)
print(df)

pipeline = CleaningPipeline()
cleaned, stats = pipeline.run(df)

print("\nCleaned df:")
print(cleaned.dtypes)
print(cleaned)

print("\nStats:")
import pprint
pprint.pprint(stats)
