"""Validator unit tests."""

import pandas as pd

from app.engine.validators.cross_file_validator import CrossFileData, validate_cross_files
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


def test_cross_file_blocks_ead_loans_missing_from_lgd() -> None:
    ead = pd.DataFrame(
        {
            "Loan ID": ["L1", "L2"],
            "SEGMENT": ["Retail", "Retail"],
            "Effective Interest Rate (EIR)": [0.1, 0.1],
        }
    )
    lgd = pd.DataFrame(
        {
            "Loan ID": ["L1"],
            "Effective Interest Rate (EIR)": [0.1],
        }
    )
    pd_df = pd.DataFrame({"Loan ID": ["L1", "L2"], "SEGMENT": ["Retail", "Retail"]})
    issues = validate_cross_files(
        CrossFileData(
            pd_combined=pd_df,
            lgd_combined=lgd,
            ead_combined=ead,
            ead_upload_id="ead1",
            ead_filename="ead.xlsx",
            lgd_upload_id="lgd1",
            lgd_filename="lgd.xlsx",
            pd_upload_id="pd1",
            pd_filename="pd.xlsx",
        )
    )
    assert any(i.level == "block" and "EC-06" in i.title for i in issues)


def test_missing_column_has_template_format_category() -> None:
    df = pd.DataFrame({"Loan ID": ["L1"]})
    result = validate_pd(df, sheet_name="Sheet1", allowed_segments={"Retail"})
    assert any(i.category == "template_format" for i in result.issues)
