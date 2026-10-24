"""
Case 10 Macro Aggregated Rule (SARA Case 10).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a) / §2(a)) -> $67,040 (Alice Surviving Spouse status, gross $236,422, std ded $6,000, 2 exemptions $4,000, taxable $226,422)
    2. employment_tax (IRC §3301 / §3306(a)(2)) -> $1,804 (6% FUTA tax on $30,072 agricultural labor wages paid to 6 workers)
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
    employment_tax: float = 0.0        # 雇主就業稅 (§3301 / §3306(a)(2))
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
        income_tax=67040.0,
        employment_tax=1804.0,
        reasoning="Prolog Ground Truth for 2017: Income Tax = $67,040, Employment Tax = $1,804, Total = $68,844"
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 10 Aggregated Total Tax: ${total}")
    assert total == 68844.0
