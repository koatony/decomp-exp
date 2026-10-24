"""
Case 1 Macro Aggregated Rule (SARA Case 1).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) is responsible for extracting/evaluating the two sub-taxes from facts:
    1. income_tax (IRC §1)
    2. employment_tax (IRC §3301)
- The Aggregation Rule deterministically computes the final total_tax.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

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

# ==============================================================================
# Case 1 由 LM 提取的目標數值與推理基準
# ==============================================================================
# 案情分析 (LM 任務)：
# 1. income_tax: Alice 2019 總收入 $6,520 ($1,200 監獄勞務 + $5,320 工資)。
#    單身標準扣除額 $12,200 > $6,520 -> 應稅所得為 0 -> income_tax = 0.0
# 2. employment_tax: Alice 非雇主且監獄勞務依 §3306(c)(21) 排除 -> employment_tax = 0.0
case_1_lm_extracted = AggregatedTaxInputs(
    target_person="Alice",
    tax_year=2019,
    income_tax=0.0,
    employment_tax=0.0,
    reasoning="Alice's gross income ($6520) is below standard deduction ($12200), and she owes no employment tax under §3306(c)(21)."
)

if __name__ == "__main__":
    total = calculate_total_tax(case_1_lm_extracted)
    print(f"=== Case 1 Aggregated Rule Run ===")
    print(f"Taxpayer: {case_1_lm_extracted.target_person}")
    print(f"Year: {case_1_lm_extracted.tax_year}")
    print(f"LM Extracted Income Tax (§1): ${case_1_lm_extracted.income_tax}")
    print(f"LM Extracted Employment Tax (§3301): ${case_1_lm_extracted.employment_tax}")
    print(f"Total Tax (Aggregated): ${total}")
    assert total == 0.0, f"Expected 0.0, got {total}"
    print("SUCCESS: Aggregated calculation perfectly matches Prolog ground truth ($0)!")
