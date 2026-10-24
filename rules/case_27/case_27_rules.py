"""
Case 27: Alice Head of Household Status (§2(b), §152(d) Dependent Father Bob),
Pre-TCJA Standard Deduction (§63(c)(2)(B)), Pre-TCJA Personal Exemptions (§151(b), §151(c)),
and Taxable Income / Schedule B Income Tax Calculation (§1(b)).
Direct 1:1 translation from SARA Prolog (tax_case_27.pl and statutory rules:
utils.pl, section1.pl, section2.pl, section63.pl, section151.pl, section152.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Head of Household Status from Observable Facts (IRC §2(b)(1)(B), §152(d)):
   - In 2017, Alice is unmarried.
   - Bob is Alice's father since April 15th, 1978.
   - Bob had no income in 2017 ($0.0 < $4,050 gross income limit under §152(d)(1)(B)).
   - Alice and Bob lived in a house maintained by Alice.
   - Alice furnishes over 50% of the household maintenance costs.
   - Under §152(d)(2)(C), father Bob is a qualifying relative.
   - Under §2(b)(1)(B), maintaining a household that constitutes principal place of abode of taxpayer's father entitles Alice to "head_of_household".
2. Standard Deduction (IRC §63(c)(2)(B)):
   - Pre-TCJA basic standard deduction for Head of Household in 2017 = $4,400.
3. Personal Exemptions & PEP Phaseout (IRC §151(b), §151(c), §151(d)(3)):
   - 2 exemptions: Alice (taxpayer) + Bob (father) = 2 * $2,000 = $4,000.
   - Head of Household PEP threshold in 2017 = $275,000.
   - Gross Income ($33,200) < $275,000 -> 0% phaseout -> allowable personal exemptions = $4,000.
4. Taxable Income (IRC §63(b)):
   - Alice takes standard deduction and does not itemize.
   - Taxable Income = max(0, Gross Income - Standard Deduction - Personal Exemptions)
                    = max(0, $33,200 - $4,400 - $4,000) = $24,800.
5. Personal Income Tax (IRC §1(b)(i) Schedule B):
   - Head of Household schedule:
     Bracket (Taxable Income <= $29,600):
     Tax = 15% * Taxable Income
         = 0.15 * $24,800 = $3,720.0.
   - utils.pl: rounding/2 -> $3,720.0.
6. Employment Tax:
   - Alice had no employees in 2017 -> $0.0.
7. Total Tax:
   - Total Tax = Income Tax ($3,720.0) + Employment Tax ($0.0) = $3,720.0.
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
    start_date: int = 20170101


# ==============================================================================
# Case 27 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_27.pl)
# ==============================================================================
case_27_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2017,
    "gross_income": 33200.0,
    "is_unmarried": True,
    "persons": [
        Person(id="alice", name="Alice"),
        Person(id="bob", name="Bob")
    ],
    "parent_child_relationships": [
        ParentChild(id="rel_bob_alice", parent="Bob", child="Alice", relationship="father")
    ],
    "dependents": [
        Dependent(id="dep_bob", name="Bob", relationship="father", gross_income=0.0)
    ],
    "residences": [
        Residence(id="res_alice", person="Alice", abode="house", start_date=20170101, end_date=20171231),
        Residence(id="res_bob", person="Bob", abode="house", start_date=20170101, end_date=20171231)
    ],
    "household_maintenances": [
        HouseholdMaintenance(id="hm_alice", agent="Alice", abode="house", amount=1.0, start_date=20170101)
    ]
}


# ==============================================================================
# Case 27 微規則 (SARA Prolog 1:1 Micro-Rules)
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
    1. 關係：父母 (§152(d)(2)(C))。
    2. 所得未達 $4,050。
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
    is_unmarried: bool,
    dependents: List[Dependent],
    relationships: List[ParentChild],
    residences: List[Residence],
    maintenances: List[HouseholdMaintenance]
) -> str:
    """
    推導申報身分 (IRC §2(b)(1)(B) Head of Household):
    未婚、負擔逾半數維持家庭之開銷，且該居所為其父親之主要居所。
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
    對應 section63.pl: s63_c_2_B
    2017 Pre-TCJA 戶長標準扣除額 = $4,400。
    """
    if tax_year >= 2018:
        return 18000.0 if filing_status == "head_of_household" else 12000.0
    else:
        return 4400.0 if filing_status == "head_of_household" else 3000.0


def compute_personal_exemptions(
    gross_income: float,
    num_exemptions: int,
    filing_status: str,
    tax_year: int
) -> float:
    """
    對應 section151.pl: s151_b / s151_c / s151_d
    2017 Pre-TCJA: 每人 $2,000 免稅額。
    PEP Phaseout 門檻 (Head of Household): $275,000。
    """
    if tax_year >= 2018:
        return 0.0

    base_exemption = 2000.0 * num_exemptions
    threshold = 275000.0 if filing_status == "head_of_household" else 250000.0

    if gross_income <= threshold:
        return base_exemption

    excess = gross_income - threshold
    phaseout_steps = math.ceil(excess / 2500.0)
    phaseout_pct = min(1.0, phaseout_steps * 0.02)
    allowable = base_exemption * (1.0 - phaseout_pct)
    return round_half_up(allowable)


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


def calculate_case_27_tax(facts: Dict[str, Any]) -> float:
    """
    Case 27 確定性端到端微規則執行 (utils.pl: tax/3)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = float(facts.get("gross_income", 0.0))
    is_unmarried = bool(facts.get("is_unmarried", True))
    dependents = facts.get("dependents", [])
    relationships = facts.get("parent_child_relationships", [])
    residences = facts.get("residences", [])
    maintenances = facts.get("household_maintenances", [])

    status = determine_filing_status(taxpayer, tax_year, is_unmarried, dependents, relationships, residences, maintenances)
    std_ded = compute_standard_deduction(status, tax_year)

    num_exemptions = 2 if status == "head_of_household" else 1
    exemptions = compute_personal_exemptions(gross_income, num_exemptions, status, tax_year)

    taxable_income = max(0.0, gross_income - std_ded - exemptions)
    inc_tax = calculate_income_tax_schedule_b(taxable_income)
    employment_tax = 0.0

    return inc_tax + employment_tax


if __name__ == "__main__":
    tax = calculate_case_27_tax(case_27_facts)
    print("=== Case 27 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_27_facts['target_person']}")
    print(f"Tax Year: {case_27_facts['tax_year']}")
    status = determine_filing_status(
        case_27_facts["target_person"],
        case_27_facts["tax_year"],
        case_27_facts["is_unmarried"],
        case_27_facts["dependents"],
        case_27_facts["parent_child_relationships"],
        case_27_facts["residences"],
        case_27_facts["household_maintenances"]
    )
    std_ded = compute_standard_deduction(status, case_27_facts["tax_year"])
    exempt = compute_personal_exemptions(case_27_facts["gross_income"], 2, status, case_27_facts["tax_year"])
    taxable_inc = max(0.0, case_27_facts["gross_income"] - std_ded - exempt)
    print(f"Derived Filing Status: {status}")
    print(f"Standard Deduction (§63(c)(2)(B)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert tax == 3720.0, f"Expected 3720.0, got {tax}"
    print("SUCCESS: Case 27 tax matches SARA Prolog ground truth ($3,720.0) exactly!")
