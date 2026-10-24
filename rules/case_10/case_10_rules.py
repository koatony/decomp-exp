"""
Case 10: Alice Surviving Spouse Status (§2(a)) & Agricultural Labor FUTA (§3301 / §3306(a)(2)).
Direct 1:1 translation from Prolog (tax_case_10.pl and statutory rules: utils.pl, section1.pl, section2.pl, section63.pl, section151.pl, section152.pl, section3301.pl, section3306.pl, section7703.pl).

Statutory Walkthrough:
1. Alice's Personal Income Tax (IRC §1(a), §2(a), §63, §151, §152, §7703):
   - Harold died on Feb 28th, 2016. Tax year is 2017 (within 2 years following spouse's death).
   - Alice has a son born Jan 25th, 2000 (age 17 in 2017, qualifying child under §152).
   - Alice furnishes 100% of household costs where she and her son live. Alice did not remarry.
   - Under IRC §2(a), Alice qualifies as a "Surviving Spouse".
   - Under IRC §63(c)(2)(A)(ii), a surviving spouse receives 200% of basic standard deduction ($3,000 * 2 = $6,000).
   - Under IRC §151, Alice is entitled to 2 personal exemptions (Alice + son Charlie) = 2 * $2,000 = $4,000.
   - Gross Income = $236,422.
   - Taxable Income = max(0, $236,422 - $6,000 - $4,000) = $226,422.
   - Under IRC §1(a)(iv) MFJ / Surviving Spouse rate schedule:
     Tax = $35,928.50 + 36% * ($226,422 - $140,000) = $35,928.50 + $31,111.92 = $67,040.42.
     Round half-up -> $67,040.0.
2. Alice's Employment Tax (FUTA IRC §3301 / §3306(a)(2)):
   - Alice employed 6 workers (Bob, Cameron, Dan, Emily, Fred, George) for agricultural labor in Sep 2017.
   - Paid each $5,012, totaling $30,072 in Q3.
   - Under IRC §3306(a)(2), paying $20,000 or more in cash for agricultural labor in any calendar quarter makes Alice an "employer".
   - Under IRC §3301, excise tax on employers = 6% of wages paid ($30,072 * 6% = $1,804.32).
   - Round half-up -> $1,804.0.
3. Total Tax (utils.pl: tax/3):
   - Total Tax = Income Tax ($67,040) + Employment Tax ($1,804) = $68,844.
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
    start_date: int        # 日期 (YYYYMMDD)
    purpose: Optional[str] = None

@dataclass
class Service:
    id: str
    agent: str             # 勞務提供者
    patient: str           # 勞務接受者
    purpose: str           # e.g. "agricultural labor"
    start_date: int
    end_date: int
    location: Optional[str] = None

@dataclass
class Dependent:
    id: str
    name: str
    parents: List[str]
    birth_date: int

@dataclass
class Marriage:
    spouse_1: str
    spouse_2: str
    start_date: int
    end_date: Optional[int] = None

@dataclass
class Death:
    person: str
    death_date: int

def round_half_up(val: float) -> float:
    """
    SARA Prolog rounding/2:
    F is float_fractional_part(In),
    F >= 0.5 -> Out is integer(float_integer_part(In)) + 1
    """
    return float(math.floor(val + 0.5))

def is_surviving_spouse(
    taxpayer: str,
    marriage: Optional[Marriage],
    death: Optional[Death],
    dependents: List[Dependent],
    tax_year: int,
    household_furnish_ratio: float = 1.0,
    remarried: bool = False
) -> bool:
    """
    IRC §2(a) Surviving Spouse:
    1. Spouse died in either of the two years immediately preceding tax_year (§2(a)(1)(A)).
    2. Maintains a household (>50% costs) which is principal place of abode of dependent child (§2(a)(1)(B)).
    3. Has not remarried before close of tax_year (§2(a)(2)).
    """
    if remarried:
        return False
    if not marriage or not death:
        return False
    
    # Check deceased spouse was married to taxpayer
    spouses = [marriage.spouse_1, marriage.spouse_2]
    if taxpayer not in spouses or death.person not in spouses:
        return False
    
    # Check death date within 2 preceding years
    death_year = death.death_date // 10000
    if not (tax_year - 2 <= death_year <= tax_year - 1):
        return False
    
    # Check household maintenance
    if household_furnish_ratio <= 0.5:
        return False
    
    # Check dependent child living with taxpayer
    has_qualifying_child = False
    for dep in dependents:
        if taxpayer in dep.parents:
            dep_birth_year = dep.birth_date // 10000
            age = tax_year - dep_birth_year
            if age < 19:  # Qualifying child age limit under §152(c)(3)
                has_qualifying_child = True
                break
                
    return has_qualifying_child

def compute_standard_deduction(
    is_surviving_spouse_status: bool,
    filing_status: str,
    tax_year: int
) -> float:
    """
    IRC §63(c)(2)(A)(ii): Surviving spouse receives 200% of basic standard deduction ($3,000 * 2 = $6,000).
    """
    if is_surviving_spouse_status or filing_status in ("married_joint", "surviving_spouse"):
        return 6000.0
    elif filing_status == "head_of_household":
        return 4400.0
    return 3000.0

def compute_personal_exemptions(
    taxpayer_count: int,
    dependent_count: int,
    tax_year: int
) -> float:
    """
    IRC §151: $2,000 per exemption in SARA benchmark.
    """
    return float((taxpayer_count + dependent_count) * 2000.0)

def compute_taxable_income(
    gross_income: float,
    standard_deduction: float,
    exemptions: float
) -> float:
    """
    IRC §63: Taxable Income = max(0, Gross Income - Standard Deduction - Exemptions).
    """
    return max(0.0, gross_income - standard_deduction - exemptions)

def calculate_income_tax_schedule_a(taxable_income: float) -> float:
    """
    IRC §1(a) Married Filing Jointly / Surviving Spouse tax bracket schedule.
    """
    if taxable_income <= 36900:
        tax = taxable_income * 0.15
    elif taxable_income <= 89150:
        tax = 5535.0 + (taxable_income - 36900.0) * 0.28
    elif taxable_income <= 140000:
        tax = 20165.0 + (taxable_income - 89150.0) * 0.31
    elif taxable_income <= 250000:
        tax = 35928.50 + (taxable_income - 140000.0) * 0.36
    else:
        tax = 75528.50 + (taxable_income - 250000.0) * 0.396
        
    return round_half_up(tax)

def calculate_agricultural_futa_tax(
    taxpayer: str,
    payments: List[Payment],
    tax_year: int
) -> float:
    """
    IRC §3301 / §3306(a)(2):
    In case of agricultural labor, an individual who pays cash remuneration of $20,000
    or more in any calendar quarter of the calendar year is an 'employer'.
    Tax = 6% of wages paid.
    """
    # Group payments by quarter
    quarterly_wages: Dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    total_wages = 0.0
    
    for p in payments:
        purpose_clean = (p.purpose or "").lower().replace("_", " ")
        if p.agent == taxpayer and "agricultural" in purpose_clean and "labor" in purpose_clean:
            pyear = p.start_date // 10000
            if pyear == tax_year:
                pmonth = (p.start_date // 100) % 100
                q = (pmonth - 1) // 3 + 1
                quarterly_wages[q] += p.amount
                total_wages += p.amount
                
    # Check $20,000 threshold in any quarter
    is_ag_employer = any(qw >= 20000.0 for qw in quarterly_wages.values())
    if not is_ag_employer:
        return 0.0
        
    return round_half_up(total_wages * 0.06)

def calculate_case_10_tax(facts: Dict[str, Any]) -> float:
    """
    End-to-end Micro-Rule calculation for Case 10:
    Total Tax = Income Tax (§1) + Employment Tax (§3301)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = facts["gross_income"]
    marriage = facts.get("marriage")
    death = facts.get("death")
    dependents = facts.get("dependents", [])
    payments = facts.get("payments", [])
    
    # 1. Surviving Spouse Status
    surviving_spouse = is_surviving_spouse(
        taxpayer=taxpayer,
        marriage=marriage,
        death=death,
        dependents=dependents,
        tax_year=tax_year,
        household_furnish_ratio=facts.get("household_furnish_ratio", 1.0),
        remarried=facts.get("remarried", False)
    )
    
    # 2. Standard Deduction & Exemptions
    std_ded = compute_standard_deduction(surviving_spouse, facts.get("filing_status", "single"), tax_year)
    exemptions = compute_personal_exemptions(1, len(dependents), tax_year)
    
    # 3. Taxable Income & Income Tax
    taxable_inc = compute_taxable_income(gross_income, std_ded, exemptions)
    income_tax = calculate_income_tax_schedule_a(taxable_inc) if surviving_spouse else 0.0
    
    # 4. Employment Tax (FUTA)
    employment_tax = calculate_agricultural_futa_tax(taxpayer, payments, tax_year)
    
    # 5. Total Tax
    return income_tax + employment_tax
