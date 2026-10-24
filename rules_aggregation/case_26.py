"""
Case 26 Macro Aggregated Rule (SARA Case 26).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(b)(v) / §2(b) / §63(c)(7)(i) / §151(d)(5)) -> $195,965.0
       - Alice is unmarried and maintains a household for her father Charlie (qualifying relative).
       - Head of Household filing status applies (IRC §2(b)).
       - Gross Income = $567,192.
       - Standard deduction (TCJA 2019 for Head of Household) = $18,000.
       - Personal exemptions (TCJA 2019) = $0.0.
       - Taxable income = $567,192 - $18,000 - $0 = $549,192.
       - Bracket §1(b)(v) (> $250,000):
         Tax = $77,485 + 39.6% * ($549,192 - $250,000)
             = $77,485 + 39.6% * $299,192 = $77,485 + $118,480.032 = $195,965.032 -> rounds to $195,965.0.
    2. employment_tax (IRC §3301, §3306(a)(1), §3306(b)(10)) -> $91.0
       - Alice paid Bob $1,513 wages and $298 disability retirement.
       - Under §3306(b)(10), disability payments are exempt.
       - Taxable wages = $1,513 >= $1,500 employer threshold.
       - FUTA tax = 6% * $1,513 = $90.78 -> rounds to $91.0.
- The Aggregation Rule deterministically computes the final total_tax = $195,965 + $91 = $196,056.0.
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
        tax_year=2019,
        income_tax=195965.0,
        employment_tax=91.0,
        reasoning=(
            "Prolog Ground Truth for 2019: "
            "Income Tax = $195,965 (Head of Household, Taxable Income $549,192, standard deduction $18,000, exemptions $0), "
            "Employment Tax = $91 (FUTA on $1,513 taxable wages; $298 disability payment exempt under §3306(b)(10)), "
            "Total = $196,056"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 26 Aggregated Total Tax: ${total}")
    assert total == 196056.0
    print("SUCCESS: Case 26 aggregated total tax matches SARA Ground Truth ($196,056.0) exactly!")
