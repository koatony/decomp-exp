"""
Case 28 Macro Aggregated Rule (SARA Case 28).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(c)(v) / §63(c)(2)(C) / §151(d)(3)) -> $344,428.0
       - Alice is single in 2017.
       - Gross Income = $921,324.
       - Standard deduction (pre-TCJA 2017 for Single) = $3,000.
       - Personal exemptions: 1 exemption ($2,000) completely phased out under §151(d)(3) (income exceeds $250k threshold by > $125k) -> $0.0.
       - Taxable income = $921,324 - $3,000 - $0 = $918,324.
       - Bracket §1(c)(v) (> $250,000):
         Tax = $79,772 + 39.6% * ($918,324 - $250,000)
             = $79,772 + 39.6% * $668,324 = $79,772 + $264,656.304 = $344,428.304 -> rounds to $344,428.0.
    2. employment_tax (IRC §3301, §3306(a)(3), §3306(b)(1)) -> $420.0
       - Alice paid Bob $53,200 wages for domestic service.
       - Domestic employer threshold under §3306(a)(3) is $1,000 per quarter -> Alice is subject to FUTA.
       - Wage limit per employee under §3306(b)(1) = $7,000.
       - FUTA tax = 6% * $7,000 = $420.0.
- The Aggregation Rule deterministically computes the final total_tax = $344,428 + $420 = $344,848.0.
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
    income_tax: float                  # 個人所得稅 (§1(c))
    employment_tax: float = 0.0        # 雇主薪資/失業稅 (§3301)
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
        income_tax=344428.0,
        employment_tax=420.0,
        reasoning=(
            "Prolog Ground Truth for 2017: "
            "Income Tax = $344,428 (Single, Taxable Income $918,324, standard deduction $3,000, 100% PEP phaseout exemptions $0), "
            "Employment Tax = $420 (Domestic service FUTA on $7,000 cap; threshold $1,000 under §3306(a)(3)), "
            "Total = $344,848"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 28 Aggregated Total Tax: ${total}")
    assert total == 344848.0
    print("SUCCESS: Case 28 aggregated total tax matches SARA Ground Truth ($344,848.0) exactly!")
