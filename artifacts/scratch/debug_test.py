import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
import numpy as np

from refineflow.cleaning.text_cleaner import TextCleaner
from refineflow.cleaning.type_fixer import TypeFixer
from refineflow.cleaning.outlier_detector import OutlierDetector

df_tc = pd.DataFrame({
    "emp_name": ["  john  doe ", "Jane\u200b Doe", "mumbai  city"],
    "emp_code": ["emp_01", "emp_02", "emp_03"],
    "city": ["Mumbi", "Delhi", "Bangalor"],
    "state": ["mh", "DL", "Pune MH"]
})
tc = TextCleaner()
res_tc = tc.run(df_tc)
print("=== Text Cleaner ===")
print("emp_name:", res_tc["emp_name"].tolist())
print("emp_code:", res_tc["emp_code"].tolist())
print("city:", res_tc["city"].tolist())
print("state:", res_tc["state"].tolist())

df_tf = pd.DataFrame({
    "order_id": [101, 102, 103],
    "price": ["$12.50", "₹150.00", "$9.99"],
    "discount": ["10%", "20%", "5%"],
    "active": ["Yes", "no", "TRUE"],
    "date_col": ["2025-05-12", "2025/05/13", "2025-05-14"],
    "city": ["Mumbai", "Delhi", "Mumbai"]
})
tf = TypeFixer()
res_tf = tf.run(df_tf)
print("\n=== Type Fixer ===")
print("order_id type:", res_tf["order_id"].dtype, res_tf["order_id"].tolist())
print("price type:", res_tf["price"].dtype, res_tf["price"].tolist())
print("active type:", res_tf["active"].dtype, res_tf["active"].tolist())
print("date_col type:", res_tf["date_col"].dtype, res_tf["date_col"].tolist())
print("city type:", res_tf["city"].dtype, res_tf["city"].tolist())

print("\n=== Outlier Detector ===")
ages = [25] * 35 + [300, -50]
df_od = pd.DataFrame({"age": ages})
od = OutlierDetector(method="iqr", action="clip")
res_od = od.run(df_od)
print("min:", res_od["age"].min())
print("max:", res_od["age"].max())
