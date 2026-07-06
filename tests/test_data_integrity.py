import sys
import os
import pandas as pd
import numpy as np

# Make sure refineflow is importable from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from refineflow.cleaning.validator import PerChunkValidator
from refineflow.cleaning.text_cleaner import TextCleaner
from refineflow.cleaning.type_fixer import TypeFixer

def test_validator_token_boundary():
    # Verify age rule matches 'age' but not 'average_gross'
    rules = {
        "age": {"type": "numeric", "min": 0, "max": 120}
    }
    validator = PerChunkValidator(rules=rules)
    df = pd.DataFrame({
        "average_gross": [13928571.0, 10353571.0, 100.0],
        "user_age": [25.0, 30.0, 150.0],  # 150 is out of bounds
        "age": [45.0, 50.0, 200.0]       # 200 is out of bounds
    })
    cleaned = validator.run(df)
    
    # average_gross should NOT be matched to age, so values should be preserved
    assert cleaned["average_gross"].iloc[0] == 13928571.0
    assert cleaned["average_gross"].iloc[1] == 10353571.0
    assert cleaned["average_gross"].iloc[2] == 100.0

    # user_age should match the age rule
    assert cleaned["user_age"].iloc[0] == 25.0
    assert pd.isna(cleaned["user_age"].iloc[2])

    # age should match the age rule
    assert cleaned["age"].iloc[0] == 45.0
    assert pd.isna(cleaned["age"].iloc[2])
    print("[PASS] test_validator_token_boundary")


def test_text_cleaner_mojibake():
    # Verify Mojibake repair for en-dash, dagger, and accents
    cleaner = TextCleaner()
    df = pd.DataFrame({
        "text": [
            "Beyonc\u00c3\u00a9",          # BeyoncÃ©
            "2023\u00e2\u20ac\u201c2024",  # 2023â€“2024
            "The Eras Tour \u00e2\u20ac\u00a0" # The Eras Tour â€\xa0
        ]
    })
    cleaned = cleaner.run(df)
    assert cleaned["text"].iloc[0] == "Beyoncé"
    assert cleaned["text"].iloc[1] == "2023–2024"
    assert cleaned["text"].iloc[2] == "The Eras Tour †"
    print("[PASS] test_text_cleaner_mojibake")


def test_type_fixer_safety():
    # Verify that TypeFixer preserves columns when conversion success is low (< 90%)
    type_fixer = TypeFixer()
    # 5 rows, only 2 are valid currency, 3 are general text (60% fail to parse)
    df = pd.DataFrame({
        "revenue": ["$100.00", "$200.00", "not currency", "invalid info", "unknown"]
    })
    cleaned = type_fixer.run(df)
    # The column should remain object type and values should be unchanged (not coerced to NaN)
    assert pd.api.types.is_string_dtype(cleaned["revenue"])
    assert cleaned["revenue"].iloc[2] == "not currency"
    
    # 10 rows, 9 are valid, 1 is invalid (90% success) -> should be converted, coercing the 1 invalid row to NaN
    df2 = pd.DataFrame({
        "revenue": ["$100", "$200", "$300", "$400", "$500", "$600", "$700", "$800", "$900", "invalid"]
    })
    cleaned2 = type_fixer.run(df2)
    assert pd.api.types.is_numeric_dtype(cleaned2["revenue"])
    assert cleaned2["revenue"].iloc[0] == 100.0
    assert pd.isna(cleaned2["revenue"].iloc[9])
    print("[PASS] test_type_fixer_safety")


if __name__ == "__main__":
    test_validator_token_boundary()
    test_text_cleaner_mojibake()
    test_type_fixer_safety()
    print("All integration tests passed successfully!")
