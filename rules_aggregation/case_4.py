"""
Case 4 Macro Aggregated Rule (SARA Case 4).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1) -> $0 (Alice gross income $4,500 < $5,000 standard deduction + exemption)
    2. employment_tax (IRC §3301 / §3306(a)(3)) -> $192 (6% FUTA tax on $3,200 domestic service wages paid to Bob)
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
    income_tax: float                  # 個人所得稅 (§1)
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
        tax_year=2012,
        income_tax=0.0,
        employment_tax=192.0,
        reasoning="Prolog Ground Truth for 2012: Income Tax = $0, Employment Tax = $192, Total = $192"
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 4 Aggregated Total Tax: ${total}")
    assert total == 192.0
