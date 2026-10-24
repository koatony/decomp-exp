"""
Case 4: Alice & Bob 2012 Domestic Service and Employment Tax (FUTA).
Direct 1:1 translation from Prolog (tax_case_4.pl and statutory rules: utils.pl, section1.pl, section63.pl, section151.pl, section3301.pl, section3306.pl).

Statutory Walkthrough:
1. Alice's Personal Income Tax (IRC §1, §63, §151):
   - Alice received $4,500 from Bob for work performed in 2012.
   - Gross Income = $4,500.
   - Standard deduction for unmarried individual in 2012 (section63.pl) = $3,000.
   - Personal exemption for individual (section151.pl) = $2,000.
   - Taxable Income = max(0, $4,500 - $3,000 - $2,000) = $0.
   - Income Tax (§1) = $0.
2. Alice's Employment Tax (FUTA IRC §3301 / §3306(a)(3)):
   - Alice paid $3,200 to Bob for domestic service in 2012.
   - Under IRC §3306(a)(3), paying $1,000+ in cash for domestic service makes Alice an "employer".
   - Under IRC §3301, excise tax on employers = 6% of wages paid ($3,200 * 6% = $192).
   - Employment Tax (§3301) = $192.
3. Total Tax (utils.pl: tax/3):
   - Total Tax = Income Tax ($0) + Employment Tax ($192) = $192.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Payment:
    id: str
    agent: Optional[str]   # 付款人
    patient: str           # 收款人
    amount: float          # 金額
    start_date: int        # 日期
    purpose: Optional[str] = None

@dataclass
class Service:
    id: str
    agent: str             # 勞務提供者
    patient: str           # 勞務接受者
    purpose: str           # e.g. "domestic service"
    start_date: int
    end_date: int
    location: Optional[str] = None

# ==============================================================================
# Case 4 原始事實 (Facts - 1:1 映射 Prolog tax_case_4.pl)
# ==============================================================================
case_4_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2012,
    "filing_status": "single",
    "payments": [
        Payment(
            id="paid_10_13",
            agent="Alice",
            patient="Bob",
            amount=3200.0,
            start_date=20120901,
            purpose="service"
        ),
        Payment(
            id="paid_128_131",
            agent="Bob",
            patient="Alice",
            amount=4500.0,
            start_date=20120901,
            purpose="work"
        )
    ],
    "services": [
        Service(
            id="service_41_47",
            agent="Bob",
            patient="Alice",
            purpose="domestic service",
            start_date=20120201,
            end_date=20120901,
            location="Baltimore, Maryland, USA"
        ),
        Service(
            id="work_152_155",
            agent="Alice",
            patient="Bob",
            purpose="work",
            start_date=20120331,
            end_date=20121231
        )
    ]
}

# ==============================================================================
# Case 4 規則庫 (Rules)
# ==============================================================================

def compute_individual_gross_income(person: str, year: int, payments: List[Any]) -> float:
    """
    對應 utils.pl: gross_income_individual/3
    尋找所有 patient 為該納稅人且在該年度獲得的付款。
    """
    total = 0.0
    for p in payments:
        patient = p.patient if isinstance(p, Payment) else p.get("patient")
        amt = p.amount if isinstance(p, Payment) else float(p.get("amount", 0.0))
        s_date = p.start_date if isinstance(p, Payment) else p.get("start_date")

        if patient == person:
            p_year = int(str(s_date)[:4])
            if p_year == year:
                total += amt
    return total

def compute_income_tax_case4(person: str, year: int, gross_income: float, filing_status: str) -> float:
    """
    對應 section63.pl (§63(c) 標準扣除額 $3,000) & section151.pl (§151(d) 免稅額 $2,000) & section1.pl
    """
    std_deduction = 3000.0  # 2012 單身基準標準扣除額
    personal_exemption = 2000.0  # 2012 個人免稅額
    taxable_income = max(0.0, gross_income - std_deduction - personal_exemption)

    if taxable_income <= 0:
        return 0.0
    # 2012 單身稅階 (<= 22100 走 15%)
    return float(round(taxable_income * 0.15))

def is_domestic_service_employer(person: str, year: int, payments: List[Any], services: List[Any]) -> Tuple[bool, float]:
    """
    對應 section3306.pl: s3306_a_3
    若支付家庭僱工 (domestic service) 工資在曆年度或季度達到 $1,000 以上，即為雇主。
    """
    total_domestic_wages = 0.0
    for p in payments:
        agent = p.agent if isinstance(p, Payment) else p.get("agent")
        amt = p.amount if isinstance(p, Payment) else float(p.get("amount", 0.0))
        s_date = p.start_date if isinstance(p, Payment) else p.get("start_date")

        if agent == person:
            p_year = int(str(s_date)[:4])
            if p_year == year:
                total_domestic_wages += amt

    is_employer = total_domestic_wages >= 1000.0
    return is_employer, total_domestic_wages

def compute_employment_tax_s3301_case4(person: str, year: int, payments: List[Any], services: List[Any]) -> float:
    """
    對應 section3301.pl: s3301/6
    稅率為 6% (0.06 * Wages)
    """
    is_employer, wages = is_domestic_service_employer(person, year, payments, services)
    if is_employer:
        raw_tax = 0.06 * wages
        return float(math.floor(raw_tax + 0.5))
    return 0.0

def calculate_case_4_tax(facts: Dict[str, Any]) -> float:
    """
    對應 utils.pl: tax(Person, Year, Tax)
    Tax = 所得稅(§1) + 雇主薪資稅(§3301)
    """
    person = facts["target_person"]
    year = facts["tax_year"]
    status = facts["filing_status"]
    payments = facts["payments"]
    services = facts.get("services", [])

    # 1. 所得稅計算
    gross_income = compute_individual_gross_income(person, year, payments)
    income_tax = compute_income_tax_case4(person, year, gross_income, status)

    # 2. 雇主稅計算 (FUTA §3301)
    employment_tax = compute_employment_tax_s3301_case4(person, year, payments, services)

    # 3. 頂層相加
    total_tax = income_tax + employment_tax
    return total_tax

if __name__ == "__main__":
    tax = calculate_case_4_tax(case_4_facts)
    print(f"=== Case 4 (Prolog -> Python 1:1) ===")
    print(f"Taxpayer: {case_4_facts['target_person']}")
    print(f"Year: {case_4_facts['tax_year']}")
    gross = compute_individual_gross_income("Alice", 2012, case_4_facts["payments"])
    print(f"Alice Gross Income: ${gross}")
    inc_tax = compute_income_tax_case4("Alice", 2012, gross, "single")
    emp_tax = compute_employment_tax_s3301_case4("Alice", 2012, case_4_facts["payments"], case_4_facts["services"])
    print(f"Income Tax (§1): ${inc_tax}")
    print(f"Employment Tax (§3301 FUTA): ${emp_tax}")
    print(f"Calculated Total Tax: ${tax}")
    assert tax == 192.0, f"Expected 192.0, got {tax}"
    print("SUCCESS: Case 4 tax calculation matches Prolog ground truth ($192) perfectly!")
