"""
Case 2 Macro Aggregated Rule (SARA Case 2).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1)
    2. employment_tax (IRC §3301)
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
    employment_tax: float = 0.0        # 雇主薪資/失業稅 (§3301)
    reasoning: Optional[str] = None    # LM 的推理依據說明

def calculate_total_tax(inputs: AggregatedTaxInputs) -> float:
    """
    頂層聚合規則 (對應 SARA utils.pl: tax/3):
    total_tax = income_tax + employment_tax
    """
    return inputs.income_tax + inputs.employment_tax

if __name__ == "__main__":
    # Case 2 Ground Truth: $26,567
    gt_inputs = AggregatedTaxInputs(
        target_person="Alice",
        tax_year=2013,
        income_tax=26567.0,
        employment_tax=0.0,
        reasoning="Prolog Ground Truth for 2013 Married Filing Jointly: $26,567"
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 2 Aggregated Total Tax: ${total}")
    assert total == 26567.0
