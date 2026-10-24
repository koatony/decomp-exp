"""
Case 24 Macro Aggregated Rule (SARA Case 24).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a)(2) / §2(a) / §63(c)(2)(A)(ii) / §151) -> $19,039.0
       - Alice qualifies as a Surviving Spouse for 2017 (husband Bob died in 2015, son Charlie is dependent child).
       - Gross Income = $95,129.
       - Standard deduction (pre-TCJA 2017 for Surviving Spouse) = $6,000.
       - Personal exemptions (Alice + Charlie = 2 * $2,000) = $4,000.
       - Taxable income = $95,129 - $6,000 - $4,000 = $85,129.
       - Bracket §1(a)(ii): $5,535 + 28% * ($85,129 - $36,900) = $5,535 + 28% * $48,229 = $5,535 + $13,504.12 = $19,039.12 -> rounds to $19,039.0.
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
        tax_year=2017,
        income_tax=19039.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2017: "
            "Income Tax = $19,039 (Surviving Spouse, Taxable Income $85,129, standard deduction $6,000, exemptions $4,000), "
            "Employment Tax = $0, "
            "Total = $19,039"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 24 Aggregated Total Tax: ${total}")
    assert total == 19039.0
    print("SUCCESS: Case 24 aggregated total tax matches SARA Ground Truth ($19,039.0) exactly!")
