"""LGD engine unit tests."""

import pandas as pd

from app.engine.lgd_engine import compute_lgd


def test_compute_lgd_proportional_collateral() -> None:
    df = pd.DataFrame(
        {
            "Customer ID": ["C1", "C1"],
            "Loan ID": ["L1", "L2"],
            "Outstanding Amount": [60_000.0, 40_000.0],
            "Effective Interest Rate (EIR)": [0.12, 0.12],
            "Property": [500_000.0, 500_000.0],
        }
    )
    config = [{"name": "Property", "haircut": 0.2, "time_to_realize": 12}]
    result = compute_lgd(df, config)
    assert len(result) == 2
    assert "Sum of Discounted Collaterals per Loan ID" in result.columns
    assert result["Sum of Discounted Collaterals per Loan ID"].sum() > 0
