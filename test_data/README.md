# ECL Dummy Test Dataset

A coherent set of `.xlsx` files for testing the ECL platform end-to-end. The
dataset is engineered to **pass every validation rule** and **exercise every
engine path** (PD transition matrix, LGD proportional-collateral allocation,
EAD forward-balance walk, and the final Stage 1 / 2 / 3 ECL aggregation).

All five files are produced by [`scripts/generate_test_data.py`](../scripts/generate_test_data.py)
and are deterministic (`random.seed(42)`). The workspace prerequisites
(Segments + Collateral Types) are seeded by
[`scripts/seed_test_workspace.py`](../scripts/seed_test_workspace.py).

---

## The dataset at a glance

| File | Purpose | Rows | Notes |
|------|---------|------|-------|
| `PD_2025_Jan_Feb.xlsx` | PD snapshots for 2025-01-31 and 2025-02-28 | 120 | Upload alongside the next PD file |
| `PD_2025_Mar_Apr.xlsx` | PD snapshots for 2025-03-31 and 2025-04-30 | 116 | The April snapshot omits 4 loans (off-books) |
| `LGD_2025_03.xlsx`     | LGD inputs as of 2025-03-31 | 60 | One row per active loan, four collateral types |
| `EAD_2025_03.xlsx`     | EAD inputs as of 2025-03-31 | 60 | Same loan cohort as LGD |

**Portfolio composition:** 60 loans across 3 segments — **Retail (30)**, **SME (20)**, **Corporate (10)**.

**Staging mix at the 2025-03-31 reporting date (drives EAD/LGD):**

| Stage   | Count |
|---------|-------|
| Stage 1 | 42    |
| Stage 2 | 6     |
| Stage 3 | 12    |

**Transition diversity across the four PD snapshots (per segment):** every
non-trivial transition is present so the engine builds a populated 3×3 matrix
per segment — `S1→S1, S1→S2, S2→S1, S2→S2, S2→S3, S3→S2, S3→S3`, plus
`S1→Off-books` (the engine's "fully repaid" boundary).

---

## Prerequisites

The dataset's `SEGMENT` and collateral column headers must exist in the target
tenant's workspace before any file will validate.

Run the seed scripts once against the `Zenith Bank` dev tenant:

```bash
cd ECL-Server
python scripts/seed_dev_data.py          # creates tenant + admin if absent
python scripts/seed_test_workspace.py    # creates 3 Segments + 4 Collateral Types
```

| Segments | Code |
|----------|------|
| Retail    | RET  |
| SME       | SME  |
| Corporate | CORP |

| Collateral Type     | Haircut % | Time to Realise (months) |
|---------------------|-----------|--------------------------|
| Real Estate         | 20.00     | 18                       |
| Motor Vehicle       | 35.00     | 6                        |
| Cash Deposit        | 0.00      | 1                        |
| Corporate Guarantee | 15.00     | 12                       |

Haircut is stored as a percentage (matches the `CollateralType.haircut`
schema, `Numeric(5,2)`, `ge=0 le=100`). The compute task layer
(`app/tasks/compute_tasks.py:187`) divides by 100 before passing the value to
the LGD engine.

---

## How to upload (dashboard → New Run)

1. Sign in as `jane@zenith.com` / `TestPass123!`.
2. Start a new run, choose **Combine: All three engines**.
3. **PD step** — drag both `PD_2025_Jan_Feb.xlsx` and `PD_2025_Mar_Apr.xlsx`. PD is the only step that accepts multiple files; the engine concatenates them and dedupes on `(Loan ID, Reporting Month)`.
4. **LGD step** — drag `LGD_2025_03.xlsx`.
5. **EAD step** — drag `EAD_2025_03.xlsx`.
6. **Validate** — expected result: **0 errors, 0 warnings** across all files.
7. **Execute** — polling resolves to `COMPLETED` with non-zero ECL.

---

## Validation rule coverage

Every error code raised by `app/engine/validators/{pd,lgd,ead}_validator.py`
is satisfied by construction:

| Code  | Rule | How this dataset satisfies it |
|-------|------|-------------------------------|
| EC-02 | LGD collateral column unknown | Column headers `Real Estate / Motor Vehicle / Cash Deposit / Corporate Guarantee` exactly match the seeded `CollateralType` rows |
| EC-03 | EAD `Maturity Date ≥ Reporting Date` | Maturities are 18–84 months **after** the reporting date |
| EC-04 | EAD `First Payment Date ≤ Reporting Date` | First payment dates are 12–36 months **before** the reporting date |
| EC-04b | EAD `Adjusted Maturity ≥ First Payment` | `Adjusted Maturity == Maturity` (no restructures simulated) |
| EC-05 | EIR in `[0, 1]` | All EIRs in `[0.11, 0.17]` |
| EC-09 | EAD `Repayment Frequency ∈ {MTH, QTR}` | `Corporate` skews `QTR`, `Retail/SME` skew `MTH` |
| EC-10 | PD duplicate `(Loan ID, Reporting Month)` | Generator guarantees uniqueness; cross-file dedup verified |

Sheet name is `"Data"` in every file (matches the validators' default).

---

## Engine paths exercised

| Engine | What this dataset hits |
|--------|-------------------------|
| **PD** (`pd_engine.compute_pd`) | 4 monthly snapshots → 3 month-to-month transition matrices, summed into a per-segment aggregate. All 3 stages appear as starting states, and the IFRS 9 boundary clamps on Stage 1 / Stage 3 rows are applied to a populated matrix. Matrix is raised to powers 1–299 to produce the lifetime PD curve (2,691 rows of `marginal_pd`). |
| **LGD** (`lgd_engine.compute_lgd`) | 60 loans, ~17 customers sharing collateral pools. Step 1 — total per customer, Step 2 — pro-rata `Proportion`, Step 3 — per-type allocation, Step 4 — `(1−haircut)·(1+EIR)^(−ttr)` discount, Step 5 — summed recovery. **53 / 60** loans receive positive recovery, **7 / 60** are uncollateralised (exercises the worst-case LGD = 100 % path). |
| **EAD** (`ead_engine.compute_ead`) | 60 loans → month-by-month forward balance walk (847 loan-month rows). Mix of `MTH` (54) and `QTR` (6) frequencies. Maturity horizons of 1.5–7 years exercise both short and long projections. Joined to the PD marginal table by `(SEGMENT, Staging, Month)` and to the LGD recovery table by `Loan ID`. **6 loans drive non-zero ECL** across **118 loan-months** (the Stage 3 cohort under IFRS 9 boundary conditions). |

---

## Smoke test (run before uploading)

```bash
cd ECL-Server
.venv/bin/python - << 'PY'
import pandas as pd
from pathlib import Path
from app.engine.validators.pd_validator import validate_pd
from app.engine.validators.lgd_validator import validate_lgd
from app.engine.validators.ead_validator import validate_ead

TEST = Path("test_data")
SEGMENTS = {"Retail", "SME", "Corporate"}
COLLATERAL = {"Real Estate", "Motor Vehicle", "Cash Deposit", "Corporate Guarantee"}

def errs(r):
    return [i for i in r.issues if i.level.lower() in ("error","block","blocking","critical")]

for f in sorted(TEST.glob("PD_*.xlsx")):
    r = validate_pd(pd.read_excel(f, sheet_name="Data"), sheet_name="Data", allowed_segments=SEGMENTS)
    assert not errs(r), f"PD {f.name}: {errs(r)}"
r = validate_lgd(pd.read_excel(TEST/"LGD_2025_03.xlsx", sheet_name="Data"), sheet_name="Data", allowed_collateral_types=COLLATERAL)
assert not errs(r), errs(r)
r = validate_ead(pd.read_excel(TEST/"EAD_2025_03.xlsx", sheet_name="Data"), sheet_name="Data", allowed_segments=SEGMENTS)
assert not errs(r), errs(r)
print("All 4 files validate cleanly.")
PY
```

---

## Regenerating

```bash
cd ECL-Server
.venv/bin/python scripts/generate_test_data.py
```

To produce a different portfolio shape, edit the two knobs at the top of the
generator: `SEGMENT_CONFIG` (counts, EIR + outstanding ranges per segment)
and `_STAGE_TRACKS` / `_classify` (per-scenario stage trajectories and their
bucket shares). All five files stay coordinated automatically — loan IDs,
customer IDs and EIRs are shared across PD / LGD / EAD by construction.
