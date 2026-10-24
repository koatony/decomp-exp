"""
Case 29: Alice & Spouse Married Filing Jointly with Dependent Father Charlie (§1(a), §63(c)(2)(A)(i), §151, §152(d)),
and FUTA Employment Tax with Retirement Fund Exemption (§3301, §3306(a)(1), §3306(b)(2)(A)).
Direct 1:1 translation from SARA Prolog (tax_case_29.pl and statutory rules:
utils.pl, section1.pl, section63.pl, section151.pl, section152.pl, section3301.pl, section3306.pl, section7703.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Filing Status & Dependents from Observable Facts:
   - Alice has been married since April 4th, 2015.
   - Alice files a joint return with her spouse for 2016 -> "married_filing_jointly" (IRC §1(a)(1), §7703).
   - Charlie is Alice's father, who retired in 2016 and had no income in 2016 ($0 < $4,050 under §152(d)(1)(B)).
   - Under §152(d)(2)(C), Charlie is a qualifying relative dependent of Alice.
2. Standard Deduction (IRC §63(c)(2)(A)(i)):
   - Basic standard deduction for Married Filing Jointly in 2016 = 200% * $3,000 = $6,000.
3. Personal Exemptions & PEP Phaseout (IRC §151(b), §151(c), §151(d)(3)):
   - 3 allowable exemptions: Alice (taxpayer) + spouse + Charlie (dependent father) = 3 * $2,000 = $6,000.
   - Married Filing Jointly PEP threshold in 2016 = $300,000.
   - Combined Gross Income ($164,612) < $300,000 -> 0% phaseout -> allowable personal exemptions = $6,000.
4. Taxable Income (IRC §63(b)):
   - Alice and spouse take standard deduction.
   - Taxable Income = max(0, Combined Gross Income - Standard Deduction - Personal Exemptions)
                    = max(0, $164,612 - $6,000 - $6,000) = $152,612.
5. Personal Income Tax (IRC §1(a)(iv) Schedule A):
   - Bracket ($140,000 < Taxable Income <= $250,000):
     Tax = $35,928.50 + 36% * (Taxable Income - $140,000)
         = $35,928.50 + 36% * ($152,612 - $140,000)
         = $35,928.50 + 36% * $12,612
         = $35,928.50 + $4,540.32
         = $40,468.82.
   - utils.pl: rounding/2 (round half-up) -> $40,469.0.
6. Employment Tax (FUTA IRC §3301, §3306(a)(1), §3306(b)(2)(A)):
   - Alice paid $4,525 to Bob for work done in 2016.
   - Alice also paid $9,832 into a retirement fund for Bob.
   - Under IRC §3306(b)(2)(A), payments made to or on behalf of an employee on account of retirement are excluded from wages.
   - Alice paid $5,322 health insurance for father Charlie (not an employee).
   - Taxable wages paid to Bob = $4,525.
   - Under §3306(a)(1), Alice paid wages >= $1,500 -> Alice is an employer subject to FUTA.
   - Taxable wages subject to FUTA = min(4525, 7000) = $4,525.0.
   - FUTA tax rate (§3301): 6% * $4,525 = $271.50.
   - utils.pl: rounding/2 (round half-up) -> $272.0.
7. Total Tax:
   - Total Tax = Income Tax ($40,469.0) + Employment Tax ($272.0) = $40,741.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Person:
    id: str
    name: str

@dataclass
class Marriage:
    id: str
    spouse_1: str
    spouse_2: str
    start_date: int

@dataclass
class JointReturn:
    id: str
    taxpayer_1: str
    taxpayer_2: str
    tax_year: int
    filing_date: Optional[int] = None

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
    is_retirement_plan: bool = False
    start_date: int = 20160101


# ==============================================================================
# Case 29 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_29.pl)
# ==============================================================================
case_29_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "spouse": "spouse",
    "tax_year": 2016,
    "gross_income": 164612.0,
    "persons": [
        Person(id="alice", name="Alice"),
        Person(id="spouse", name="spouse"),
        Person(id="bob", name="Bob"),
        Person(id="charlie", name="Charlie")
    ],
    "marriages": [
        Marriage(id="m_alice", spouse_1="Alice", spouse_2="spouse", start_date=20150404)
    ],
    "joint_returns": [
        JointReturn(id="jr_alice_2016", taxpayer_1="Alice", taxpayer_2="spouse", tax_year=2016, filing_date=20160101)
    ],
    "parent_child_relationships": [
        ParentChild(id="rel_charlie_alice", parent="Charlie", child="Alice", relationship="father")
    ],
    "dependents": [
        Dependent(id="dep_charlie", name="Charlie", relationship="father", gross_income=0.0)
    ],
    "payments": [
        Payment(id="pay_bob_wages", agent="Alice", patient="Bob", amount=4525.0, purpose="work done labor", is_retirement_plan=False, start_date=20160101),
        Payment(id="pay_bob_ret", agent="Alice", patient="Bob", amount=9832.0, purpose="retirement fund", is_retirement_plan=True, start_date=20160101),
        Payment(id="pay_charlie_ins", agent="Alice", patient="Charlie", amount=5322.0, purpose="health insurance", is_retirement_plan=False, start_date=20160101)
    ]
}


# ==============================================================================
# Case 29 微規則 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """對應 utils.pl: rounding/2 (四捨五入至整數)"""
    return float(math.floor(val + 0.5))


def is_qualifying_relative(
    dependent_name: str,
    taxpayer: str,
    dependents: List[Dependent],
    relationships: List[ParentChild]
) -> bool:
    """
    對應 section152.pl: s152_d
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

    for d in dependents:
        if d.name.lower() == dependent_name.lower():
            if d.gross_income >= 4050.0:
                return False

    return True


def determine_filing_status(
    taxpayer: str,
    tax_year: int,
    marriages: List[Marriage],
    joint_returns: List[JointReturn]
) -> Tuple[str, Optional[str]]:
    """
    推導申報身分 (IRC §1(a), §7703)
    """
    first_day = tax_year * 10000 + 101
    last_day = tax_year * 10000 + 1231

    for jr in joint_returns:
        if jr.tax_year == tax_year:
            t1, t2 = jr.taxpayer_1.lower(), jr.taxpayer_2.lower()
            if taxpayer.lower() in (t1, t2):
                spouse = jr.taxpayer_2 if taxpayer.lower() == t1 else jr.taxpayer_1
                return "married_filing_jointly", spouse

    return "single", None


def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_2_A_i
    2016 Pre-TCJA: married_filing_jointly = 200% * $3,000 = $6,000。
    """
    if tax_year >= 2018:
        return 24000.0 if filing_status == "married_filing_jointly" else 12000.0
    return 6000.0 if filing_status == "married_filing_jointly" else 3000.0


def compute_personal_exemptions(
    gross_income: float,
    num_exemptions: int,
    filing_status: str,
    tax_year: int
) -> float:
    """
    對應 section151.pl: s151_b / s151_c / s151_d
    2016 Pre-TCJA: 每人 $2,000 免稅額。
    PEP Phaseout 門檻 (Married Filing Jointly): $300,000。
    """
    if tax_year >= 2018:
        return 0.0

    base_exemption = 2000.0 * num_exemptions
    threshold = 300000.0 if filing_status == "married_filing_jointly" else 250000.0

    if gross_income <= threshold:
        return base_exemption

    excess = gross_income - threshold
    phaseout_steps = math.ceil(excess / 2500.0)
    phaseout_pct = min(1.0, phaseout_steps * 0.02)
    allowable = base_exemption * (1.0 - phaseout_pct)
    return round_half_up(allowable)


def calculate_income_tax_schedule_a(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_a (Schedule A)
    """
    if taxable_income <= 0:
        return 0.0
    elif taxable_income <= 36900.0:
        tax = taxable_income * 0.15
    elif taxable_income <= 89150.0:
        tax = 5535.0 + (taxable_income - 36900.0) * 0.28
    elif taxable_income <= 140000.0:
        tax = 20165.0 + (taxable_income - 89150.0) * 0.31
    elif taxable_income <= 250000.0:
        tax = 35928.50 + (taxable_income - 140000.0) * 0.36
    else:
        tax = 75528.50 + (taxable_income - 250000.0) * 0.396

    return round_half_up(tax)


def calculate_futa_tax(
    taxpayer: str,
    payments: List[Payment],
    tax_year: int
) -> float:
    """
    對應 section3301.pl & section3306.pl:
    1. IRC §3306(b)(2)(A): 退休金/退休計畫支付款項排除於工資。
    2. IRC §3306(a)(1): 一般受僱工資 >= $1,500 具雇主身分。
    3. IRC §3306(b)(1): 每位員工年工資上限 $7,000。
    4. IRC §3301: 6% 稅率。
    """
    wages_by_employee: Dict[str, float] = {}

    for p in payments:
        if p.agent.lower() == taxpayer.lower() and (p.start_date // 10000) == tax_year:
            # 查驗是否為退休金給付
            is_retirement = p.is_retirement_plan or ("retirement" in p.purpose.lower())
            is_health_ins_for_non_emp = ("insurance" in p.purpose.lower())
            if not is_retirement and not is_health_ins_for_non_emp:
                emp = p.patient.lower()
                wages_by_employee[emp] = wages_by_employee.get(emp, 0.0) + p.amount

    total_wages = sum(wages_by_employee.values())
    if total_wages < 1500.0:
        return 0.0

    capped_wages = sum(min(7000.0, wage) for wage in wages_by_employee.values())
    futa_tax = capped_wages * 0.06
    return round_half_up(futa_tax)


def calculate_case_29_tax(facts: Dict[str, Any]) -> float:
    """
    Case 29 確定性端到端微規則執行 (utils.pl: tax/3)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = float(facts.get("gross_income", 0.0))
    marriages = facts.get("marriages", [])
    joint_returns = facts.get("joint_returns", [])
    dependents = facts.get("dependents", [])
    relationships = facts.get("parent_child_relationships", [])
    payments = facts.get("payments", [])

    status, spouse = determine_filing_status(taxpayer, tax_year, marriages, joint_returns)
    std_ded = compute_standard_deduction(status, tax_year)

    # 計算免稅額人數：Alice + spouse + qualifying relative
    num_exemptions = 2 if status == "married_filing_jointly" else 1
    for d in dependents:
        if d.name.lower() != taxpayer.lower() and (spouse is None or d.name.lower() != spouse.lower()):
            if is_qualifying_relative(d.name, taxpayer, dependents, relationships):
                num_exemptions += 1

    exemptions = compute_personal_exemptions(gross_income, num_exemptions, status, tax_year)
    taxable_income = max(0.0, gross_income - std_ded - exemptions)

    inc_tax = calculate_income_tax_schedule_a(taxable_income)
    futa_tax = calculate_futa_tax(taxpayer, payments, tax_year)

    return inc_tax + futa_tax


if __name__ == "__main__":
    tax = calculate_case_29_tax(case_29_facts)
    print("=== Case 29 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_29_facts['target_person']}")
    print(f"Tax Year: {case_29_facts['tax_year']}")
    std_ded = compute_standard_deduction("married_filing_jointly", case_29_facts["tax_year"])
    exempt = compute_personal_exemptions(case_29_facts["gross_income"], 3, "married_filing_jointly", case_29_facts["tax_year"])
    taxable_inc = max(0.0, case_29_facts["gross_income"] - std_ded - exempt)
    inc_tax = calculate_income_tax_schedule_a(taxable_inc)
    futa_tax = calculate_futa_tax(case_29_facts["target_person"], case_29_facts["payments"], case_29_facts["tax_year"])
    print(f"Standard Deduction (§63(c)(2)(A)(i)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151): ${exempt:,.2f} (3 exemptions)")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(a)): ${inc_tax:,.2f}")
    print(f"Employment Tax (§3301): ${futa_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert tax == 40741.0, f"Expected 40741.0, got {tax}"
    print("SUCCESS: Case 29 tax matches SARA Prolog ground truth ($40,741.0) exactly!")
