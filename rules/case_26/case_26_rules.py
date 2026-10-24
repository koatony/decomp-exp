"""
Case 26: Alice Head of Household Status (§2(b), §152(d) Dependent Father Charlie),
TCJA Standard Deduction (§63(c)(7)(i)), TCJA Personal Exemptions (§151(d)(5)),
Schedule B Top Bracket Income Tax (§1(b)(v)), and FUTA Employment Tax with Disability Exemption (§3301, §3306(a)(1), §3306(b)(10)).
Direct 1:1 translation from SARA Prolog (tax_case_26.pl and statutory rules:
utils.pl, section1.pl, section2.pl, section63.pl, section151.pl, section152.pl, section3301.pl, section3306.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Head of Household Status from Observable Facts (IRC §2(b)(1)(B), §152(d)):
   - Alice is unmarried in 2019.
   - Charlie is Alice's father.
   - Charlie had no income in 2019 ($0 < $4,050 gross income test under §152(d)(1)(B)).
   - Alice and Charlie lived together in a house maintained by Alice.
   - Alice furnishes over 50% of the household maintenance costs.
   - Under §152(d)(2)(C), father is a qualifying relative.
   - Under §2(b)(1)(B), maintaining a household that constitutes principal place of abode of taxpayer's father entitles Alice to "head_of_household".
2. Standard Deduction (IRC §63(c)(2)(B), §63(c)(7)(i)):
   - TCJA basic standard deduction for Head of Household (2018-2025) = $18,000.
3. Personal Exemptions (IRC §151(d)(5)):
   - TCJA exemption amount is $0.0.
4. Taxable Income (IRC §63(b)):
   - Alice takes standard deduction.
   - Gross Income = $567,192.
   - Taxable Income = max(0, $567,192 - $18,000 - $0) = $549,192.
5. Personal Income Tax (IRC §1(b)(v) Schedule B Top Bracket):
   - Bracket (Taxable Income > $250,000):
     Tax = $77,485 + 39.6% * (Taxable Income - $250,000)
         = $77,485 + 39.6% * ($549,192 - $250,000)
         = $77,485 + 39.6% * $299,192
         = $77,485 + $118,480.032
         = $195,965.032.
   - utils.pl: rounding/2 (round half-up) -> $195,965.0.
6. Employment Tax (FUTA IRC §3301, §3306(a)(1), §3306(b)(10)):
   - Alice employed Bob from 2011 to 2019, paying him $1,513 for work done in 2019.
   - Alice also paid Bob $298 on account of contract termination due to Bob's disability.
   - Under IRC §3306(b)(10), payments on account of retirement for disability are excluded from taxable wages.
   - Taxable wages paid to Bob = $1,513.
   - Under IRC §3306(a)(1), Alice is an employer because taxable wages paid in calendar year/quarter >= $1,500.
   - Taxable wages subject to FUTA = $1,513 (<= $7,000 annual limit under §3306(b)(1)).
   - FUTA tax rate (§3301): 6% * $1,513 = $90.78.
   - utils.pl: rounding/2 (round half-up) -> $91.0.
7. Total Tax:
   - Total Tax = Income Tax ($195,965.0) + Employment Tax ($91.0) = $196,056.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Person:
    id: str
    name: str
    birth_date: Optional[int] = None

@dataclass
class ParentChild:
    id: str
    parent: str
    child: str
    relationship: str = "father"

@dataclass
class Dependent:
    id: str
    name: str
    relationship: str
    gross_income: float = 0.0

@dataclass
class Payment:
    id: str
    agent: str             # payer
    patient: str           # payee
    amount: float
    purpose: str
    is_disability_retirement: bool = False
    start_date: int = 20190101

@dataclass
class Service:
    id: str
    agent: str             # employee
    patient: str           # employer
    start_date: int
    end_date: int

@dataclass
class Residence:
    id: str
    person: str
    abode: str
    start_date: int
    end_date: int

@dataclass
class HouseholdMaintenance:
    id: str
    agent: str
    abode: str
    amount: float = 1.0
    start_date: int = 20190101


# ==============================================================================
# Case 26 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_26.pl)
# ==============================================================================
case_26_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2019,
    "gross_income": 567192.0,
    "is_unmarried": True,
    "persons": [
        Person(id="alice", name="Alice"),
        Person(id="charlie", name="Charlie"),
        Person(id="bob", name="Bob")
    ],
    "parent_child_relationships": [
        ParentChild(id="rel_charlie_alice", parent="Charlie", child="Alice", relationship="father")
    ],
    "dependents": [
        Dependent(id="dep_charlie", name="Charlie", relationship="father", gross_income=0.0)
    ],
    "payments": [
        Payment(id="pay_bob_wages", agent="Alice", patient="Bob", amount=1513.0, purpose="employment labor", is_disability_retirement=False, start_date=20190101),
        Payment(id="pay_bob_disability", agent="Alice", patient="Bob", amount=298.0, purpose="disability contract termination", is_disability_retirement=True, start_date=20191010)
    ],
    "services": [
        Service(id="serv_bob", agent="Bob", patient="Alice", start_date=20110101, end_date=20191010)
    ],
    "residences": [
        Residence(id="res_alice", person="Alice", abode="house", start_date=20190101, end_date=20191231),
        Residence(id="res_charlie", person="Charlie", abode="house", start_date=20190101, end_date=20191231)
    ],
    "household_maintenances": [
        HouseholdMaintenance(id="hm_alice", agent="Alice", abode="house", amount=1.0, start_date=20190101)
    ]
}


# ==============================================================================
# Case 26 微規則 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """對應 utils.pl: rounding/2 (四捨五入至整數)"""
    return float(math.floor(val + 0.5))


def is_qualifying_relative(
    dependent_name: str,
    taxpayer: str,
    tax_year: int,
    dependents: List[Dependent],
    relationships: List[ParentChild]
) -> bool:
    """
    對應 section152.pl: s152_d (Qualifying Relative)
    1. 關係：父母、子女、兄弟姊妹等 (§152(d)(2))。
    2. 所得：gross income < $4,050 (§152(d)(1)(B))。
    """
    is_parent = any(
        r.child.lower() == taxpayer.lower() and r.parent.lower() == dependent_name.lower()
        for r in relationships
    )
    if not is_parent:
        is_parent = any(
            d.name.lower() == dependent_name.lower() and d.relationship.lower() in ("father", "mother", "parent")
            for d in dependents
        )
    if not is_parent:
        return False

    # 查驗所得
    for d in dependents:
        if d.name.lower() == dependent_name.lower():
            if d.gross_income >= 4050.0:
                return False

    return True


def determine_filing_status(
    taxpayer: str,
    tax_year: int,
    is_unmarried: bool,
    dependents: List[Dependent],
    relationships: List[ParentChild],
    residences: List[Residence],
    maintenances: List[HouseholdMaintenance]
) -> str:
    """
    推導申報身分 (IRC §2(b)(1)(B) Head of Household):
    未婚、負擔逾半數維持家庭之開銷，且該居所為其符合 §152 資格之父母的主要居所。
    """
    if not is_unmarried:
        return "single"

    maintains_home = any(
        m.agent.lower() == taxpayer.lower() and (m.amount if m.amount is not None else 1.0) >= 0.5
        for m in maintenances
    )
    if not maintains_home:
        for r in residences:
            if r.person.lower() == taxpayer.lower() or taxpayer.lower() in r.abode.lower():
                maintains_home = True
                break

    if not maintains_home:
        return "single"

    taxpayer_abodes = {
        r.abode for r in residences
        if r.person.lower() == taxpayer.lower() or taxpayer.lower() in r.abode.lower()
    }
    if not taxpayer_abodes and residences:
        taxpayer_abodes = {r.abode for r in residences}

    for d in dependents:
        if d.name.lower() != taxpayer.lower():
            if is_qualifying_relative(d.name, taxpayer, tax_year, dependents, relationships):
                parent_in_abode = any(
                    r.person.lower() == d.name.lower() and r.abode in taxpayer_abodes
                    for r in residences
                )
                if parent_in_abode:
                    return "head_of_household"

    return "single"


def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_7_i
    2019 TCJA 戶長標準扣除額 = $18,000。
    """
    if tax_year >= 2018:
        return 18000.0 if filing_status == "head_of_household" else 12000.0
    else:
        return 4400.0 if filing_status == "head_of_household" else 3000.0


def compute_personal_exemptions(tax_year: int) -> float:
    """
    對應 section151.pl: s151_d_5
    2019 TCJA 個人免稅額 = $0.0。
    """
    if 2018 <= tax_year <= 2025:
        return 0.0
    return 4000.0


def calculate_income_tax_schedule_b(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_b (Schedule B)
    """
    if taxable_income <= 0:
        return 0.0
    elif taxable_income <= 29600.0:
        tax = taxable_income * 0.15
    elif taxable_income <= 76400.0:
        tax = 4440.0 + (taxable_income - 29600.0) * 0.28
    elif taxable_income <= 127500.0:
        tax = 17544.0 + (taxable_income - 76400.0) * 0.31
    elif taxable_income <= 250000.0:
        tax = 33385.0 + (taxable_income - 127500.0) * 0.36
    else:
        tax = 77485.0 + (taxable_income - 250000.0) * 0.396

    return round_half_up(tax)


def calculate_futa_tax(
    taxpayer: str,
    payments: List[Payment],
    tax_year: int
) -> float:
    """
    對應 section3301.pl & section3306.pl:
    1. IRC §3306(b)(10): 因殘疾退休支付之款項排除於工資之外。
    2. IRC §3306(a)(1): 支付非免稅工資達 $1,500 即具備雇主身分。
    3. IRC §3306(b)(1): 每位員工工資上限 $7,000。
    4. IRC §3301: 6% 稅率。
    """
    taxable_wages_by_employee: Dict[str, float] = {}

    for p in payments:
        if p.agent.lower() == taxpayer.lower() and (p.start_date // 10000) == tax_year:
            # 檢查是否屬於 §3306(b)(10) 殘疾退休給付
            is_disability = p.is_disability_retirement or ("disability" in p.purpose.lower())
            if not is_disability:
                emp = p.patient.lower()
                taxable_wages_by_employee[emp] = taxable_wages_by_employee.get(emp, 0.0) + p.amount

    total_wages = sum(taxable_wages_by_employee.values())

    # §3306(a)(1) 雇主門檻：任一季度或年度達 $1,500
    if total_wages < 1500.0:
        return 0.0

    # 每人 $7,000 上限
    capped_wages = sum(min(7000.0, wage) for wage in taxable_wages_by_employee.values())
    futa_tax = capped_wages * 0.06
    return round_half_up(futa_tax)


def calculate_case_26_tax(facts: Dict[str, Any]) -> float:
    """
    Case 26 確定性端到端微規則執行 (utils.pl: tax/3)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = float(facts.get("gross_income", 0.0))
    is_unmarried = bool(facts.get("is_unmarried", True))
    dependents = facts.get("dependents", [])
    relationships = facts.get("parent_child_relationships", [])
    residences = facts.get("residences", [])
    maintenances = facts.get("household_maintenances", [])
    payments = facts.get("payments", [])

    # 1. 判定申報身分
    status = determine_filing_status(taxpayer, tax_year, is_unmarried, dependents, relationships, residences, maintenances)

    # 2. 標準扣除額
    std_ded = compute_standard_deduction(status, tax_year)

    # 3. 個人免稅額 (TCJA 2019 = $0)
    exemptions = compute_personal_exemptions(tax_year)

    # 4. 應稅所得
    taxable_income = max(0.0, gross_income - std_ded - exemptions)

    # 5. 所得稅額
    inc_tax = calculate_income_tax_schedule_b(taxable_income)

    # 6. 雇主失業稅 (FUTA)
    emp_tax = calculate_futa_tax(taxpayer, payments, tax_year)

    return inc_tax + emp_tax


if __name__ == "__main__":
    tax = calculate_case_26_tax(case_26_facts)
    print("=== Case 26 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_26_facts['target_person']}")
    print(f"Tax Year: {case_26_facts['tax_year']}")
    status = determine_filing_status(
        case_26_facts["target_person"],
        case_26_facts["tax_year"],
        case_26_facts["is_unmarried"],
        case_26_facts["dependents"],
        case_26_facts["parent_child_relationships"],
        case_26_facts["residences"],
        case_26_facts["household_maintenances"]
    )
    std_ded = compute_standard_deduction(status, case_26_facts["tax_year"])
    exempt = compute_personal_exemptions(case_26_facts["tax_year"])
    taxable_inc = max(0.0, case_26_facts["gross_income"] - std_ded - exempt)
    inc_tax = calculate_income_tax_schedule_b(taxable_inc)
    futa_tax = calculate_futa_tax(case_26_facts["target_person"], case_26_facts["payments"], case_26_facts["tax_year"])
    print(f"Derived Filing Status: {status}")
    print(f"Standard Deduction (§63(c)(7)(i)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151(d)(5)): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(b)): ${inc_tax:,.2f}")
    print(f"Employment Tax (§3301): ${futa_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert tax == 196056.0, f"Expected 196056.0, got {tax}"
    print("SUCCESS: Case 26 tax matches SARA Prolog ground truth ($196,056.0) exactly!")
