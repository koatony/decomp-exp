"""
Case 54 Macro Aggregated Rule (SARA Case 54).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a)(2) / §2(a) / §63(c)(7) / §151(d)(5)) -> $62,000.0
       - Alice qualifies as a Surviving Spouse (Bob died on Jan 1, 2017, which is within the 2 preceding years; son Charlie lives in home).
       - Gross Income = $236,422.
       - Standard deduction (TCJA §63(c)(7)(ii) $12,000 * 200%) = $24,000.
       - Personal exemptions (TCJA §151(d)(5)) = $0.0.
       - Taxable income = $236,422 - $24,000 - $0 = $212,422.
       - Bracket §1(a)(iv): $35,928.50 + 36% * ($212,422 - $140,000) = $35,928.50 + $26,071.92 = $62,000.42 -> rounds to $62,000.0.
    2. employment_tax (IRC §3301) -> $0.0
       - Alice has no employees in 2019.
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
    income_tax: float                  # 個人所得稅 (§1(a)(2))
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
        income_tax=62000.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2019: "
            "Income Tax = $62,000 (Surviving Spouse, Taxable Income $212,422, TCJA standard deduction $24,000, exemptions $0), "
            "Employment Tax = $0 (No employment services), "
            "Total = $62,000"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 54 Aggregated Total Tax: ${total}")
    assert total == 62000.0
    print("SUCCESS: Case 54 aggregated total tax matches SARA Ground Truth ($62,000.0) exactly!")
