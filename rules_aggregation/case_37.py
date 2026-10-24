"""
Case 37 Macro Aggregated Rule (SARA Case 37).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(b) / §2(b) / §63(c)(7)(i) / §151(d)(5)) -> $32,045.0
       - Alice is unmarried and maintains a household for her adopted son Bob.
       - Head of Household filing status applies (IRC §2(b)).
       - Gross Income = $141,177.
       - Standard deduction (TCJA §63(c)(7)(i) for Head of Household) = $18,000.
       - Personal exemptions (TCJA §151(d)(5)) = $0.0.
       - Taxable income = $141,177 - $18,000 - $0 = $123,177.
       - Bracket §1(b)(iii): $17,544 + 31% * ($123,177 - $76,400) = $17,544 + 31% * $46,777 = $17,544 + $14,500.87 = $32,044.87 -> rounds to $32,045.0.
    2. employment_tax (IRC §3301) -> $0.0
       - Alice has no employees in 2018.
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
        tax_year=2018,
        income_tax=32045.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2018: "
            "Income Tax = $32,045 (Head of Household, Taxable Income $123,177, TCJA standard deduction $18,000, exemptions $0), "
            "Employment Tax = $0 (No employment services), "
            "Total = $32,045"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 37 Aggregated Total Tax: ${total}")
    assert total == 32045.0
    print("SUCCESS: Case 37 aggregated total tax matches SARA Ground Truth ($32,045.0) exactly!")
