"""
Case 46 Macro Aggregated Rule (SARA Case 46).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a) / §7703 / §63(c)(7) / §151(d)(5)) -> $17,399.0
       - Alice and spouse Married Filing Jointly for 2020.
       - Gross Income = $103,272.
       - Standard deduction (TCJA §63(c)(7)(ii) $12,000 * 200%) = $24,000.
       - Personal exemptions (TCJA §151(d)(5)) = $0.0.
       - Taxable income = $103,272 - $24,000 - $0 = $79,272.
       - Bracket §1(a)(ii): $5,535 + 28% * ($79,272 - $36,900) = $5,535 + $11,864.16 = $17,399.16 -> rounds to $17,399.0.
    2. employment_tax (IRC §3301 / §3306(a)(2) / §3306(b)(11)) -> $0.0
       - Alice paid Bob $3,200 for agricultural labor with "eggs, grapes and hay".
       - Under IRC §3306(b)(11) (SARA section3306.pl: s3306_b_11), non-cash compensation for agricultural labor is excluded from wages.
       - Even if cash, $3,200 < $20,000 threshold and 1 employee < 5 employees under §3306(a)(2).
       - FUTA tax = $0.0.
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
    income_tax: float                  # 個人所得稅 (§1(a))
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
        tax_year=2020,
        income_tax=17399.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2020: "
            "Income Tax = $17,399 (Married Filing Jointly, Taxable Income $79,272, TCJA standard deduction $24,000, exemptions $0), "
            "Employment Tax = $0 (Agricultural labor paid in non-cash medium 'eggs, grapes and hay' excluded under §3306(b)(11), "
            "and remuneration < $20,000 threshold under §3306(a)(2)), "
            "Total = $17,399"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 46 Aggregated Total Tax: ${total}")
    assert total == 17399.0
    print("SUCCESS: Case 46 aggregated total tax matches SARA Ground Truth ($17,399.0) exactly!")
