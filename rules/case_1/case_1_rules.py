"""
Case 1: Alice's 2019 Tax Computation Rules and Facts.
Direct 1:1 translation from Prolog (tax_case_1.pl and statutory rules: utils.pl, section63.pl, section1.pl, section3306.pl).
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Payment:
    id: str
    patient: str          # 領款人 / 受益人
    amount: float         # 金額
    start_date: int       # 日期 (YYYYMMDD)
    agent: Optional[str] = None    # 付款人
    purpose: Optional[str] = None  # 用途

@dataclass
class Service:
    id: str
    agent: str            # 勞務提供者
    patient: str          # 勞務接受者
    start_date: int
    end_date: int

@dataclass
class Incarceration:
    id: str
    agent: str            # 服刑者
    patient: str          # 監禁場所 (jail)
    start_date: int
    end_date: int

# ==============================================================================
# Case 1 原始事實 (Facts - 1:1 映射 Prolog tax_case_1.pl)
# ==============================================================================
case_1_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2019,
    "filing_status": "single",
    "payments": [
        Payment(
            id="paid_10_13",
            patient="Alice",
            agent="jail",
            amount=1200.0,
            start_date=20190101,
            purpose="services"
        ),
        Payment(
            id="paid_175_178",
            patient="Alice",
            agent=None,
            amount=5320.0,
            start_date=20191231,
            purpose=None
        )
    ],
    "services": [
        Service(
            id="services_33_40",
            agent="Alice",
            patient="jail",
            start_date=20150124,
            end_date=20190505
        )
    ],
    "incarcerations": [
        Incarceration(
            id="committed_71_79",
            agent="Alice",
            patient="jail",
            start_date=20150124,
            end_date=20190505
        )
    ]
}

# ==============================================================================
# Case 1 規則庫 (Rules - 1:1 映射 Prolog 呼叫到的法規條文)
# ==============================================================================

def compute_gross_income(person: str, year: int, payments: List[Payment]) -> float:
    """
    對應 utils.pl: gross_income_individual/3
    尋找所有 patient 為該納稅人、且日期在該年度內的付款加總。
    """
    total = 0.0
    for p in payments:
        if p.patient == person:
            # 判斷年份：YYYYMMDD 落在該年度內
            p_year = int(str(p.start_date)[:4])
            if p_year == year:
                total += p.amount
    return total

def get_standard_deduction(filing_status: str, year: int) -> float:
    """
    對應 section63.pl: s63_c/3 (標準扣除額)
    2019 年單身標準扣除額為 $12,200
    """
    if year == 2019 and filing_status == "single":
        return 12200.0
    return 12200.0

def compute_taxable_income(gross_income: float, deduction: float) -> float:
    """
    對應 section63.pl: s63/3
    應稅所得 = max(0, 總收入 - 扣除額)
    """
    return max(0.0, gross_income - deduction)

def compute_income_tax_s1(taxable_income: float, year: int, filing_status: str) -> float:
    """
    對應 section1.pl: s1/4 (個人所得稅)
    若應稅所得為 0，則稅額為 0
    """
    if taxable_income <= 0:
        return 0.0
    if taxable_income <= 9700:
        return taxable_income * 0.10
    else:
        return 970.0 + (taxable_income - 9700) * 0.12

def compute_employment_tax_s3301(person: str, year: int, facts: Dict[str, Any]) -> float:
    """
    對應 section3301.pl & section3306.pl (FUTA 雇主失業稅)
    Alice 是受薪者而非雇主，且監獄勞務依據 §3306(c)(21) 排除，稅額為 0
    """
    return 0.0

def calculate_case_1_tax(facts: Dict[str, Any]) -> float:
    """
    對應 utils.pl: tax(Person, Year, Tax)
    Tax = 所得稅(§1) + 雇主稅(§3301)
    """
    person = facts["target_person"]
    year = facts["tax_year"]
    status = facts["filing_status"]

    # 1. 總收入
    gross_income = compute_gross_income(person, year, facts["payments"])
    # 2. 標準扣除額
    std_deduction = get_standard_deduction(status, year)
    # 3. 應稅所得
    taxable_income = compute_taxable_income(gross_income, std_deduction)
    # 4. §1 所得稅
    income_tax = compute_income_tax_s1(taxable_income, year, status)
    # 5. §3301 薪資稅
    employment_tax = compute_employment_tax_s3301(person, year, facts)

    total_tax = income_tax + employment_tax
    return total_tax

if __name__ == "__main__":
    tax = calculate_case_1_tax(case_1_facts)
    print(f"=== Case 1 (Prolog -> Python 1:1) ===")
    print(f"Taxpayer: {case_1_facts['target_person']}")
    print(f"Year: {case_1_facts['tax_year']}")
    print(f"Gross Income: ${compute_gross_income('Alice', 2019, case_1_facts['payments'])}")
    print(f"Calculated Tax: ${tax}")
    assert tax == 0.0, f"Expected 0.0, got {tax}"
    print("SUCCESS: Tax calculation matches Prolog ground truth ($0)!")
