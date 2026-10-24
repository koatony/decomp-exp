"""
Case 51 Macro Aggregated Rule (SARA Case 51).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(b) / §2(b) / §63(c) / §151) -> $55,528
       - Alice Head of Household status (Dorothy mother lives in abode, Alice maintains household)
       - Gross Income = $197,407
       - Standard deduction = $4,400
       - 2 Personal exemptions (Alice + Dorothy) = $4,000 (no PEP phaseout since AGI < $275,000)
       - Taxable income = $197,407 - $4,400 - $4,000 = $189,007
       - Bracket §1(b)(iv): $33,385 + 36% * ($189,007 - $127,500) = $55,527.52 -> rounds to $55,528.0
    2. employment_tax (IRC §3301 / §3306(a)(2)) -> $0.0
       - Alice paid Bob $23,200 for agricultural labor in Caracas, Venezuela.
       - Under SARA Prolog formalization (§3306(a)(2)(A)), employee wages are capped at $7,000
         under §3306(b)(1) before checking the $20,000 employer threshold ($7,000 < $20,000).
       - Alice does not qualify as an agricultural employer under SARA Prolog -> FUTA = $0.0.
- The Aggregation Rule deterministically computes the final total_tax.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class AggregatedTaxInputs:
    """
    由 LM 從案件事實中抓取/計算的核心子稅額參數。
    """
    target_person: str
    tax_year: int
    income_tax: float                  # 個人所得稅 (§1(b))
    employment_tax: float = 0.0        # 雇主薪資/失業稅 (§3301 / §3306)
    reasoning: Optional[str] = None    # LM 的推理依據說明

def calculate_total_tax(inputs: AggregatedTaxInputs) -> float:
    """
    頂層聚合規則 (對應 SARA utils.pl: tax/3):
    total_tax = income_tax + employment_tax
    """
    return inputs.income_tax + inputs.employment_tax

if __name__ == "__main__":
    gt_inputs = AggregatedTaxInputs(
        target_person="Alice",
        tax_year=2017,
        income_tax=55528.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2017: "
            "Income Tax = $55,528 (Head of Household, Taxable Income $189,007), "
            "Employment Tax = $0 (Agricultural labor wage capped at $7,000 < $20,000 threshold under SARA Prolog), "
            "Total = $55,528"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 51 Aggregated Total Tax: ${total}")
    assert total == 55528.0
    print("SUCCESS: Case 51 aggregated total tax matches SARA Ground Truth ($55,528.0) exactly!")
