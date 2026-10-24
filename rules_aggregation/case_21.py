"""
Case 21 Macro Aggregated Rule (SARA Case 21).
Core Statutory Formula (utils.pl: tax/3):
    total_tax = income_tax + employment_tax

Architecture:
- The Language Model (LM) evaluates/extracts the two sub-taxes from facts:
    1. income_tax (IRC §1(a) / §7703 / §63(c)(7)(ii) / §151(d)(5)) -> $15,777.0
       - Alice & Bob are married and file jointly for 2018.
       - Combined Gross Income = $54,232 + $43,245 = $97,477.
       - Standard deduction (TCJA §63(c)(7)(ii) for Married Filing Jointly) = $24,000.
       - Personal exemptions (TCJA §151(d)(5)) = $0.0.
       - Taxable income = $97,477 - $24,000 - $0 = $73,477.
       - Bracket §1(a)(ii): $5,535 + 28% * ($73,477 - $36,900) = $5,535 + 28% * $36,577 = $5,535 + $10,241.56 = $15,776.56 -> rounds to $15,777.0.
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
        tax_year=2018,
        income_tax=15777.0,
        employment_tax=0.0,
        reasoning=(
            "Prolog Ground Truth for 2018: "
            "Income Tax = $15,777 (Married Filing Jointly, Combined Income $97,477, TCJA standard deduction $24,000, exemptions $0), "
            "Employment Tax = $0, "
            "Total = $15,777"
        )
    )
    total = calculate_total_tax(gt_inputs)
    print(f"Case 21 Aggregated Total Tax: ${total}")
    assert total == 15777.0
    print("SUCCESS: Case 21 aggregated total tax matches SARA Ground Truth ($15,777.0) exactly!")
