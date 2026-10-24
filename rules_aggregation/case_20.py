"""
Case 20 Macro Aggregated Rule (SARA Case 20).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a) / §2(a) / §68 / §151(d)(3)) -> $90,263
    2. employment_tax (IRC §3301 / §3306(b)(1)/(2)) -> $420
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
    employment_tax: float = 0.0        # 雇主就業稅 (§3301 / §3306)
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
        income_tax=90263.0,
        employment_tax=420.0,
        reasoning="Prolog Ground Truth for 2017: Income Tax = $90,263, Employment Tax = $420, Total = $90,683"
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 20 Aggregated Total Tax: ${total}")
    assert total == 90683.0
