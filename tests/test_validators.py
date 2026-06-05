"""Validator unit tests."""

import pandas as pd

from app.engine.validators.ead_validator import validate_ead
from app.engine.validators.pd_validator import validate_pd


def test_pd_validator_rejects_unknown_segment() -> None:
    df = pd.DataFrame(
        {
            "Loan ID": ["L1"],
            "Reporting Month": pd.to_datetime(["2024-01-31"]),
            "Staging": ["Stage 1"],
            "Loan Amount": [1000.0],
            "SEGMENT": ["Unknown"],
        }
    )
    result = validate_pd(df, sheet_name="Sheet1", allowed_segments={"Retail"})
    assert not result.is_valid
    assert any(i.level == "block" for i in result.issues)


def test_ead_validator_ec03_maturity_before_reporting() -> None:
    df = pd.DataFrame(
        {
            "Loan ID": ["L1"],
            "Customer ID": ["C1"],
            "SEGMENT": ["Retail"],
            "Reporting Date": pd.to_datetime(["2024-06-01"]),
            "Maturity Date": pd.to_datetime(["2024-01-01"]),
            "Adjusted Maturity Date": pd.to_datetime(["2024-12-01"]),
            "First Payment Date": pd.to_datetime(["2023-01-01"]),
            "Staging": ["Stage 1"],
            "Outstanding Amount": [100_000.0],
            "Effective Interest Rate (EIR)": [0.1],
            "Repayment Frequency": ["MTH"],
        }
    )
    result = validate_ead(df, sheet_name="Sheet1", allowed_segments={"Retail"})
    assert not result.is_valid
