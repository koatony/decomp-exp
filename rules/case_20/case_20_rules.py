"""
Case 20: Alice Surviving Spouse, Itemized Deductions (§63/§68), Exemption Phaseout (§151(d)(3)),
and Employment Tax Wage Base Cap (§3301 / §3306(b)(1)/(2)).
Direct 1:1 translation from Prolog (tax_case_20.pl and statutory rules: utils.pl, section1.pl, section2.pl, section63.pl, section68.pl, section151.pl, section152.pl, section3301.pl, section3306.pl).

Statutory Walkthrough:
1. Surviving Spouse Status (IRC §2(a)):
   - Husband died on Nov 23rd, 2016. Tax year 2017.
   - Alice maintains home where she and daughter live. Alice did not remarry.
   - Alice qualifies as "Surviving Spouse".
2. Itemized Deductions & Pease Limitation (IRC §63(d), §68):
   - Claimed itemized deductions = $17,890.
   - Applicable threshold for Surviving Spouse = $300,000.
   - AGI = $310,192. Excess = $10,192.
   - Reduction = min(3% of $10,192, 80% of $17,890) = round_half_up(305.76) = $306.
   - Allowable itemized deductions = $17,890 - $306 = $17,584.
3. Personal Exemptions & PEP Phaseout (IRC §151, §152):
   - 3 exemptions: Alice, daughter (qualifying child), and Charlie (father, retired, no income, qualifying relative).
   - Exemption phaseout percentage = 2% * ceil(10,192 / 2,500) = 2% * 5 = 10%.
   - Reduction per exemption = round_half_up(2,000 * 10%) = $200.
   - Net exemption amount = $1,800 each. Total exemptions = 3 * $1,800 = $5,400.
4. Taxable Income & Income Tax (IRC §1(a)(v)):
   - Taxable Income = $310,192 - $17,584 - $5,400 = $287,208.
   - Tax = $75,528.50 + 39.6% * ($287,208 - $250,000) = $75,528.50 + $14,734.368 = $90,262.868.
   - Round half-up -> $90,263.0.
5. FUTA Employment Tax (IRC §3301, §3306(b)(1), §3306(b)(2)):
   - Paid Bob $45,252 for work -> capped at $7,000 under §3306(b)(1).
   - Paid Bob $9,832 into retirement fund under plan -> excluded under §3306(b)(2).
   - Paid Charlie $5,322 into health insurance under plan -> excluded under §3306(b)(2).
   - Taxable wages = $7,000. FUTA Tax = $7,000 * 6% = $420.0.
6. Total Tax:
   - Total Tax = $90,263.0 + $420.0 = $90,683.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import math

@dataclass
class Payment:
    id: str
    agent: Optional[str]
    patient: str
    amount: float
    start_date: int
    purpose: Optional[str] = None
    is_plan: bool = False
    beneficiary: Optional[str] = None

@dataclass
class Dependent:
    id: str
    name: str
    relationship: str      # "daughter", "father", etc.
    parents: Optional[List[str]] = None
    gross_income: float = 0.0

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
    return float(math.floor(val + 0.5))

def is_surviving_spouse(
    taxpayer: str,
    marriage: Optional[Marriage],
    death: Optional[Death],
    has_dependent_child: bool,
    tax_year: int,
    household_furnish_ratio: float = 1.0,
    remarried: bool = False
) -> bool:
    if remarried or not marriage or not death:
        return False
    spouses = [marriage.spouse_1, marriage.spouse_2]
    if taxpayer not in spouses or death.person not in spouses:
        return False
    death_year = death.death_date // 10000
    if not (tax_year - 2 <= death_year <= tax_year - 1):
        return False
    if household_furnish_ratio <= 0.5:
        return False
    return has_dependent_child

def compute_pease_itemized_deductions(
    gross_income: float,
    claimed_itemized_deductions: float,
    filing_status: str,
    tax_year: int
) -> float:
    """
    IRC §68: Overall limitation on itemized deductions.
    Applicable amount: $300,000 for Surviving Spouse / MFJ; $275,000 for HoH; $250,000 for Single; $150,000 for MFS.
    """
    if filing_status in ("married_joint", "surviving_spouse"):
        threshold = 300000.0
    elif filing_status == "head_of_household":
        threshold = 275000.0
    elif filing_status == "single":
        threshold = 250000.0
    else:
        threshold = 150000.0
        
    if gross_income <= threshold:
        return claimed_itemized_deductions
        
    excess = gross_income - threshold
    red1 = round_half_up(excess * 0.03)
    red2 = round_half_up(claimed_itemized_deductions * 0.80)
    reduction = min(red1, red2)
    return max(0.0, claimed_itemized_deductions - reduction)

def compute_pep_exemptions(
    gross_income: float,
    exemption_count: int,
    filing_status: str,
    tax_year: int
) -> float:
    """
    IRC §151(d)(3): Personal exemption phaseout (PEP).
    Base exemption = $2,000.
    Applicable percentage: 2 percentage points for each $2,500 (or fraction thereof) over threshold.
    """
    if filing_status in ("married_joint", "surviving_spouse"):
        threshold = 300000.0
    elif filing_status == "head_of_household":
        threshold = 275000.0
    elif filing_status == "single":
        threshold = 250000.0
    else:
        threshold = 150000.0
        
    base_ea = 2000.0
    if gross_income <= threshold:
        return float(exemption_count * base_ea)
        
    diff = gross_income - threshold
    step = 1250.0 if filing_status == "married_separate" else 2500.0
    num_steps = math.ceil(diff / step)
    app_pct = min(100.0, 2.0 * num_steps)
    reduction_per_ea = round_half_up((base_ea * app_pct) / 100.0)
    net_ea = max(0.0, base_ea - reduction_per_ea)
    return float(exemption_count * net_ea)

def calculate_income_tax_schedule_a(taxable_income: float) -> float:
    """
    IRC §1(a) Surviving Spouse / MFJ bracket.
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

def calculate_case_20_futa(
    taxpayer: str,
    payments: List[Payment],
    tax_year: int
) -> float:
    """
    IRC §3301, §3306(b)(1), §3306(b)(2):
    FUTA excise tax on employers.
    - Excludes plan payments (§3306(b)(2)).
    - Caps remuneration per individual at $7,000 (§3306(b)(1)).
    - 6% tax rate.
    """
    wages_by_employee: Dict[str, float] = {}
    
    for p in payments:
        if p.agent == taxpayer:
            # Exclude plan payments (retirement/health insurance)
            if p.is_plan or (p.purpose and any(w in p.purpose.lower() for w in ["retirement", "health", "insurance", "plan"])):
                continue
            # Non-plan employee work wages
            wages_by_employee[p.patient] = wages_by_employee.get(p.patient, 0.0) + p.amount
            
    # Apply $7,000 cap per employee (§3306(b)(1))
    total_capped_wages = 0.0
    for emp, wage in wages_by_employee.items():
        capped = min(7000.0, wage)
        total_capped_wages += capped
        
    if total_capped_wages < 1500.0:  # §3306(a)(1) employer threshold
        return 0.0
        
    return round_half_up(total_capped_wages * 0.06)

def calculate_case_20_tax(facts: Dict[str, Any]) -> float:
    """
    Complete deterministic micro-rules execution for Case 20.
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = facts["gross_income"]
    claimed_itemized = facts.get("claimed_itemized_deductions", 0.0)
    marriage = facts.get("marriage")
    death = facts.get("death")
    dependents = facts.get("dependents", [])
    payments = facts.get("payments", [])
    
    has_daughter = any(d.relationship == "daughter" for d in dependents)
    surviving_spouse = is_surviving_spouse(
        taxpayer=taxpayer,
        marriage=marriage,
        death=death,
        has_dependent_child=has_daughter,
        tax_year=tax_year,
        household_furnish_ratio=facts.get("household_furnish_ratio", 1.0),
        remarried=facts.get("remarried", False)
    )
    
    status = "surviving_spouse" if surviving_spouse else facts.get("filing_status", "single")
    
    # 1. Deductions: Itemized with Pease Limitation
    deductions = compute_pease_itemized_deductions(gross_income, claimed_itemized, status, tax_year)
    
    # 2. Exemptions with PEP Phaseout (Alice + Daughter + Father Charlie = 3)
    exemption_cnt = 1 + len(dependents)
    exemptions = compute_pep_exemptions(gross_income, exemption_cnt, status, tax_year)
    
    # 3. Taxable Income & Income Tax
    taxable_income = max(0.0, gross_income - deductions - exemptions)
    income_tax = calculate_income_tax_schedule_a(taxable_income)
    
    # 4. Employment Tax (FUTA)
    emp_tax = calculate_case_20_futa(taxpayer, payments, tax_year)
    
    return income_tax + emp_tax
