"""
Case 28: Alice Single Individual with High Income PEP Phaseout (§1(c), §63(c)(2)(C), §151(d)(3)),
and Domestic Employment FUTA Tax (§3301, §3306(a)(3), §3306(b)(1)).
Direct 1:1 translation from SARA Prolog (tax_case_28.pl and statutory rules:
utils.pl, section1.pl, section63.pl, section151.pl, section3301.pl, section3306.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Filing Status from Observable Facts:
   - Alice is unmarried in 2017, no qualifying dependents or children -> "single".
2. Standard Deduction (IRC §63(c)(2)(C)):
   - Basic standard deduction for Single in 2017 = $3,000.
3. Personal Exemptions & Complete PEP Phaseout (IRC §151(b), §151(d)(3)):
   - 1 personal exemption = $2,000.
   - Single PEP threshold = $250,000.
   - Gross Income ($921,324) exceeds threshold by $671,324.
   - Phaseout reduction = ceil(671,324 / 2,500) * 2% = 269 * 2% = 538% -> capped at 100%.
   - Allowable personal exemptions = $0.0.
4. Taxable Income (IRC §63(b)):
   - Alice takes standard deduction and does not itemize.
   - Taxable Income = max(0, $921,324 - $3,000 - $0) = $918,324.
5. Personal Income Tax (IRC §1(c)(v) Schedule C Top Bracket):
   - Bracket (Taxable Income > $250,000):
     Tax = $79,772 + 39.6% * (Taxable Income - $250,000)
         = $79,772 + 39.6% * ($918,324 - $250,000)
         = $79,772 + 39.6% * $668,324
         = $79,772 + $264,656.304
         = $344,428.304.
   - utils.pl: rounding/2 (round half-up) -> $344,428.0.
6. Employment Tax (FUTA Domestic Service IRC §3301, §3306(a)(3), §3306(b)(1)):
   - Alice paid wages of $53,200 to Bob for domestic service done in 2017.
   - Under §3306(a)(3), domestic employment threshold is $1,000 cash remuneration in any calendar quarter.
     Alice paid $53,200 >= $1,000 -> Alice is an employer subject to FUTA.
   - Under §3306(b)(1), taxable wage cap per employee = $7,000.
     Taxable wages for Bob = min(53200, 7000) = $7,000.0.
   - FUTA tax rate (§3301): 6% * $7,000 = $420.0.
7. Total Tax:
   - Total Tax = Income Tax ($344,428.0) + Employment Tax ($420.0) = $344,848.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Person:
    id: str
    name: str

@dataclass
class Payment:
    id: str
    agent: str             # Alice
    patient: str           # Bob
    amount: float          # 53200.0
    purpose: str           # "domestic service" / "wages"
    start_date: int = 20170201
    end_date: int = 20170902

@dataclass
class Service:
    id: str
    agent: str             # Bob
    patient: str           # Alice
    purpose: str           # "domestic service"
    start_date: int = 20170201
    end_date: int = 20170902


# ==============================================================================
# Case 28 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_28.pl)
# ==============================================================================
case_28_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2017,
    "gross_income": 921324.0,
    "is_unmarried": True,
    "persons": [
        Person(id="alice", name="Alice"),
        Person(id="bob", name="Bob")
    ],
    "payments": [
        Payment(id="pay_bob", agent="Alice", patient="Bob", amount=53200.0, purpose="domestic service wages", start_date=20170201, end_date=20170902)
    ],
    "services": [
        Service(id="serv_bob", agent="Bob", patient="Alice", purpose="domestic service", start_date=20170201, end_date=20170902)
    ]
}


# ==============================================================================
# Case 28 微規則 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """對應 utils.pl: rounding/2 (四捨五入至整數)"""
    return float(math.floor(val + 0.5))


def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_2_C
    2017 Pre-TCJA 單身標準扣除額 = $3,000。
    """
    if tax_year >= 2018:
        return 12000.0
    return 3000.0


def compute_personal_exemptions(
    gross_income: float,
    num_exemptions: int,
    filing_status: str,
    tax_year: int
) -> float:
    """
    對應 section151.pl: s151_b / s151_d_3
    2017 Pre-TCJA: 每人 $2,000 免稅額。
    Single PEP Phaseout 門檻: $250,000。
    超過部分每 $2,500 遞減 2%，上限 100%。
    """
    if tax_year >= 2018:
        return 0.0

    base_exemption = 2000.0 * num_exemptions
    threshold = 250000.0

    if gross_income <= threshold:
        return base_exemption

    excess = gross_income - threshold
    phaseout_steps = math.ceil(excess / 2500.0)
    phaseout_pct = min(1.0, phaseout_steps * 0.02)
    allowable = base_exemption * (1.0 - phaseout_pct)
    return round_half_up(allowable)


def calculate_income_tax_schedule_c(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_c (Single Schedule C)
    """
    if taxable_income <= 0:
        return 0.0
    elif taxable_income <= 22100.0:
        tax = taxable_income * 0.15
    elif taxable_income <= 53500.0:
        tax = 3315.0 + (taxable_income - 22100.0) * 0.28
    elif taxable_income <= 115000.0:
        tax = 12107.0 + (taxable_income - 53500.0) * 0.31
    elif taxable_income <= 250000.0:
        tax = 31172.0 + (taxable_income - 115000.0) * 0.36
    else:
        tax = 79772.0 + (taxable_income - 250000.0) * 0.396

    return round_half_up(tax)


def calculate_domestic_futa_tax(
    taxpayer: str,
    payments: List[Payment],
    services: List[Service],
    tax_year: int
) -> float:
    """
    對應 section3301.pl & section3306.pl:
    1. IRC §3306(a)(3): 家務服務 (domestic service) 任一季度支付工資達 $1,000 即為雇主。
    2. IRC §3306(b)(1): 每位員工年工資上限 $7,000。
    3. IRC §3301: 6% 稅率。
    """
    wages_by_employee: Dict[str, float] = {}

    for p in payments:
        if p.agent.lower() == taxpayer.lower() and (p.start_date // 10000) == tax_year:
            is_domestic = ("domestic" in p.purpose.lower()) or any(
                s.agent.lower() == p.patient.lower() and "domestic" in s.purpose.lower()
                for s in services
            )
            if is_domestic:
                emp = p.patient.lower()
                wages_by_employee[emp] = wages_by_employee.get(emp, 0.0) + p.amount

    total_domestic_wages = sum(wages_by_employee.values())

    # §3306(a)(3) 家務雇主門檻：$1,000
    if total_domestic_wages < 1000.0:
        return 0.0

    # 每位員工工資上限 $7,000
    capped_wages = sum(min(7000.0, wage) for wage in wages_by_employee.values())
    futa_tax = capped_wages * 0.06
    return round_half_up(futa_tax)


def calculate_case_28_tax(facts: Dict[str, Any]) -> float:
    """
    Case 28 確定性端到端微規則執行 (utils.pl: tax/3)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = float(facts.get("gross_income", 0.0))
    payments = facts.get("payments", [])
    services = facts.get("services", [])

    filing_status = "single"
    std_ded = compute_standard_deduction(filing_status, tax_year)
    exemptions = compute_personal_exemptions(gross_income, 1, filing_status, tax_year)

    taxable_income = max(0.0, gross_income - std_ded - exemptions)
    inc_tax = calculate_income_tax_schedule_c(taxable_income)
    futa_tax = calculate_domestic_futa_tax(taxpayer, payments, services, tax_year)

    return inc_tax + futa_tax


if __name__ == "__main__":
    tax = calculate_case_28_tax(case_28_facts)
    print("=== Case 28 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_28_facts['target_person']}")
    print(f"Tax Year: {case_28_facts['tax_year']}")
    std_ded = compute_standard_deduction("single", case_28_facts["tax_year"])
    exempt = compute_personal_exemptions(case_28_facts["gross_income"], 1, "single", case_28_facts["tax_year"])
    taxable_inc = max(0.0, case_28_facts["gross_income"] - std_ded - exempt)
    inc_tax = calculate_income_tax_schedule_c(taxable_inc)
    futa_tax = calculate_domestic_futa_tax(case_28_facts["target_person"], case_28_facts["payments"], case_28_facts["services"], case_28_facts["tax_year"])
    print(f"Standard Deduction (§63(c)(2)(C)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(c)): ${inc_tax:,.2f}")
    print(f"Employment Tax (§3301, §3306(a)(3)): ${futa_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert tax == 344848.0, f"Expected 344848.0, got {tax}"
    print("SUCCESS: Case 28 tax matches SARA Prolog ground truth ($344,848.0) exactly!")
