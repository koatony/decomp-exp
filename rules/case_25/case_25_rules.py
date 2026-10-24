"""
Case 25: Alice & Charlie Married Filing Jointly (IRC §1(a), §7703),
TCJA Standard Deduction (§63(c)(7)(ii)), TCJA Personal Exemptions (§151(d)(5)),
and Taxable Income / Schedule A Top Bracket Income Tax Calculation (§1(a)(v)).
Direct 1:1 translation from SARA Prolog (tax_case_25.pl and statutory rules:
utils.pl, section1.pl, section63.pl, section151.pl, section7703.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Marital Status & Filing Status from Observable Facts (IRC §7703, §1(a)):
   - Alice and Charlie married on August 8th, 2018.
   - Marriage is legally recognized and intact at the close of taxable year 2018 (IRC §7703(a)).
   - Alice and Charlie make a single return jointly for taxable year 2018 (IRC §1(a)(1)).
   - Deterministic derivation: Filing status evaluates to "married_filing_jointly".
2. Combined Gross Income:
   - Alice's gross income in 2018 = $324,311.
   - Charlie's gross income in 2018 = $414,231.
   - Combined Gross Income = $324,311 + $414,231 = $738,542.
3. Standard Deduction (IRC §63(c)(2)(A), §63(c)(7)(ii)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section63.pl: s63_c_7_ii),
     basic standard deduction for joint return = 200% * $12,000 = $24,000.
4. Personal Exemptions (IRC §151(d)(5)):
   - Under TCJA (2018-2025), exemption amount is explicitly $0.0.
5. Taxable Income (IRC §63(b)):
   - Alice and Charlie take standard deduction and do not itemize.
   - Taxable Income = max(0, Combined Gross Income - Standard Deduction - Personal Exemptions)
                    = max(0, $738,542 - $24,000 - $0) = $714,542.
6. Personal Income Tax (IRC §1(a)(v) Schedule A Top Bracket):
   - Married filing jointly schedule:
     Bracket (Taxable Income > $250,000):
     Tax = $75,528.50 + 39.6% * (Taxable Income - $250,000)
         = $75,528.50 + 39.6% * ($714,542 - $250,000)
         = $75,528.50 + 39.6% * $464,542
         = $75,528.50 + $183,958.632
         = $259,487.132.
   - utils.pl: rounding/2 (round half-up) -> $259,487.0.
7. Employment Tax:
   - No employment services in 2018 -> $0.0.
8. Total Tax:
   - Total Tax = Income Tax ($259,487.0) + Employment Tax ($0.0) = $259,487.0.
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
class Marriage:
    id: str
    spouse_1: str
    spouse_2: str
    start_date: int                    # YYYYMMDD
    end_date: Optional[int] = None     # YYYYMMDD

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
    relationship: str = "son"

@dataclass
class Residence:
    id: str
    person: str
    abode: str
    start_date: int
    end_date: int


# ==============================================================================
# Case 25 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_25.pl)
# ==============================================================================
case_25_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "spouse": "Charlie",
    "tax_year": 2018,
    "gross_income": 324311.0,
    "spouse_gross_income": 414231.0,
    "persons": [
        Person(id="alice", name="Alice"),
        Person(id="charlie", name="Charlie"),
        Person(id="bob", name="Bob", birth_date=20150415),
        Person(id="dorothy", name="Dorothy")
    ],
    "marriages": [
        Marriage(id="m_alice_charlie", spouse_1="Alice", spouse_2="Charlie", start_date=20180808)
    ],
    "joint_returns": [
        JointReturn(id="jr_alice_charlie_2018", taxpayer_1="Alice", taxpayer_2="Charlie", tax_year=2018, filing_date=20180101)
    ],
    "parent_child_relationships": [
        ParentChild(id="rel_charlie_bob", parent="Charlie", child="Bob", relationship="son"),
        ParentChild(id="rel_dorothy_bob", parent="Dorothy", child="Bob", relationship="son")
    ],
    "residences": [
        Residence(id="res_alice", person="Alice", abode="home", start_date=20180101, end_date=20181231),
        Residence(id="res_bob", person="Bob", abode="home", start_date=20180101, end_date=20181231),
        Residence(id="res_charlie", person="Charlie", abode="home", start_date=20180101, end_date=20181231)
    ]
}


# ==============================================================================
# Case 25 微規則 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """對應 utils.pl: rounding/2 (四捨五入至整數)"""
    return float(math.floor(val + 0.5))


def is_married_under_s7703(
    person1: str,
    person2: str,
    marriages: List[Marriage],
    tax_year: int
) -> bool:
    """
    對應 section7703.pl: s7703
    查驗在該年度內婚姻是否存續。
    """
    first_day = tax_year * 10000 + 101
    last_day = tax_year * 10000 + 1231

    for m in marriages:
        spouses = {m.spouse_1.lower(), m.spouse_2.lower()}
        if person1.lower() in spouses and person2.lower() in spouses:
            if m.start_date <= last_day:
                if m.end_date is None or m.end_date >= first_day:
                    return True
    return False


def determine_filing_status(
    taxpayer: str,
    tax_year: int,
    marriages: List[Marriage],
    joint_returns: List[JointReturn]
) -> Tuple[str, Optional[str]]:
    """
    推導申報身分 (IRC §1(a), §7703)
    """
    for jr in joint_returns:
        if jr.tax_year == tax_year:
            t1, t2 = jr.taxpayer_1.lower(), jr.taxpayer_2.lower()
            if taxpayer.lower() in (t1, t2):
                spouse = jr.taxpayer_2 if taxpayer.lower() == t1 else jr.taxpayer_1
                if is_married_under_s7703(taxpayer, spouse, marriages, tax_year):
                    return "married_filing_jointly", spouse

    return "single", None


def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_7_ii
    2018 TCJA: married_filing_jointly = 200% * $12,000 = $24,000。
    """
    if tax_year >= 2018:
        if filing_status in ("married_filing_jointly", "surviving_spouse"):
            return 24000.0
        elif filing_status == "head_of_household":
            return 18000.0
        else:
            return 12000.0
    else:
        return 6000.0 if filing_status in ("married_filing_jointly", "surviving_spouse") else 3000.0


def compute_personal_exemptions(filing_status: str, tax_year: int) -> float:
    """
    對應 section151.pl: s151_d_5
    2018 TCJA: 個人免稅額降為 $0.0。
    """
    if 2018 <= tax_year <= 2025:
        return 0.0
    return 4000.0


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


def calculate_case_25_tax(facts: Dict[str, Any]) -> float:
    """
    Case 25 確定性端到端微規則執行 (utils.pl: tax/3)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = float(facts.get("gross_income", 0.0))
    spouse_gross_income = float(facts.get("spouse_gross_income", 0.0))
    marriages = facts.get("marriages", [])
    joint_returns = facts.get("joint_returns", [])

    status, spouse = determine_filing_status(taxpayer, tax_year, marriages, joint_returns)

    total_gross = gross_income + (spouse_gross_income if status == "married_filing_jointly" else 0.0)
    std_ded = compute_standard_deduction(status, tax_year)
    exemptions = compute_personal_exemptions(status, tax_year)

    taxable_income = max(0.0, total_gross - std_ded - exemptions)

    if status == "married_filing_jointly":
        inc_tax = calculate_income_tax_schedule_a(taxable_income)
    else:
        inc_tax = 0.0

    employment_tax = 0.0
    return inc_tax + employment_tax


if __name__ == "__main__":
    tax = calculate_case_25_tax(case_25_facts)
    print("=== Case 25 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_25_facts['target_person']}")
    print(f"Tax Year: {case_25_facts['tax_year']}")
    status, spouse = determine_filing_status(
        case_25_facts["target_person"],
        case_25_facts["tax_year"],
        case_25_facts["marriages"],
        case_25_facts["joint_returns"]
    )
    total_gross = case_25_facts["gross_income"] + case_25_facts["spouse_gross_income"]
    std_ded = compute_standard_deduction(status, case_25_facts["tax_year"])
    exempt = compute_personal_exemptions(status, case_25_facts["tax_year"])
    taxable_inc = max(0.0, total_gross - std_ded - exempt)
    print(f"Derived Filing Status: {status} (Spouse: {spouse})")
    print(f"Combined Gross Income: ${total_gross:,.2f}")
    print(f"Standard Deduction (§63(c)(7)(ii)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151(d)(5)): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert tax == 259487.0, f"Expected 259487.0, got {tax}"
    print("SUCCESS: Case 25 tax matches SARA Prolog ground truth ($259,487.0) exactly!")
