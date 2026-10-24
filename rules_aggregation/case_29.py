"""
Case 29 Macro Aggregated Rule (SARA Case 29).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a)(iv) / §63(c)(2)(A)(i) / §151(b), §151(c)) -> $40,469.0
       - Alice & spouse file jointly in 2016, claiming dependent father Charlie (3 exemptions).
       - Gross Income = $164,612.
       - Standard deduction (pre-TCJA 2016 for Married Jointly) = $6,000.
       - Personal exemptions: 3 * $2,000 = $6,000.
       - Taxable income = $164,612 - $6,000 - $6,000 = $152,612.
       - Bracket §1(a)(iv): $35,928.50 + 36% * ($152,612 - $140,000) = $35,928.50 + 36% * $12,612 = $35,928.50 + $4,540.32 = $40,468.82 -> rounds to $40,469.0.
    2. employment_tax (IRC §3301, §3306(a)(1), §3306(b)(2)(A)) -> $272.0
       - Alice paid Bob $4,525 wages and $9,832 into retirement fund.
       - Retirement payments are exempt under §3306(b)(2)(A).
       - Taxable wages = $4,525 >= $1,500 employer threshold.
       - FUTA tax = 6% * $4,525 = $271.50 -> rounds to $272.0.
- The Aggregation Rule deterministically computes the final total_tax = $40,469 + $272 = $40,741.0.
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
        tax_year=2016,
        income_tax=40469.0,
        employment_tax=272.0,
        reasoning=(
            "Prolog Ground Truth for 2016: "
            "Income Tax = $40,469 (Married Filing Jointly, 3 exemptions, Taxable Income $152,612, standard deduction $6,000, exemptions $6,000), "
            "Employment Tax = $272 (FUTA on $4,525 wages; retirement payments exempt under §3306(b)(2)(A)), "
            "Total = $40,741"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 29 Aggregated Total Tax: ${total}")
    assert total == 40741.0
    print("SUCCESS: Case 29 aggregated total tax matches SARA Ground Truth ($40,741.0) exactly!")
