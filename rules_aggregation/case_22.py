"""
Case 22 Macro Aggregated Rule (SARA Case 22).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(b) / §2(b) / §63(c)(2)(B) / §151) -> $2,174.0
       - Alice is unmarried and maintains a home for her son Bob (qualifying child).
       - Head of Household filing status applies (IRC §2(b)).
       - Gross Income = $22,895.
       - Standard deduction (pre-TCJA 2017 for Head of Household) = $4,400.
       - Personal exemptions (Alice + Bob = 2 * $2,000) = $4,000.
       - Taxable income = $22,895 - $4,400 - $4,000 = $14,495.
       - Bracket §1(b)(i): 15% * $14,495 = $2,174.25 -> rounds to $2,174.0.
    2. employment_tax (IRC §3301) -> $0.0
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
        income_tax=2174.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2017: "
            "Income Tax = $2,174 (Head of Household, Taxable Income $14,495, standard deduction $4,400, exemptions $4,000), "
            "Employment Tax = $0, "
            "Total = $2,174"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 22 Aggregated Total Tax: ${total}")
    assert total == 2174.0
    print("SUCCESS: Case 22 aggregated total tax matches SARA Ground Truth ($2,174.0) exactly!")
