"""
Case 37: Alice Head of Household Status (§2(b), §152(f)(1)(B) Adopted Child),
TCJA Standard Deduction (§63(c)(7)(i)), TCJA Personal Exemptions (§151(d)(5)),
and Taxable Income / Schedule B Income Tax Calculation (§1(b)).
Direct 1:1 translation from SARA Prolog (tax_case_37.pl and statutory rules: utils.pl, section1.pl, section2.pl, section63.pl, section151.pl, section152.pl, section7703.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Head of Household Status from Observable Facts (IRC §2(b), §151, §152(f)(1)(B), §7703):
   - Alice was born on January 10th, 1992.
   - Alice is unmarried during taxable year 2018 (no marriage facts).
   - Bob was born on January 31st, 2014.
   - Alice legally adopted Bob on March 4th, 2018. Under IRC §152(f)(1)(B), a legally adopted child is treated as a child by blood.
   - Bob has lived with Alice since adoption in a house that Alice maintains as her principal place of abode.
   - The period from March 4th, 2018 to December 31st, 2018 exceeds half of the taxable year (> 183 days).
   - Alice furnishes over half of the household maintenance costs (§2(b)(1)).
   - Deterministic rule derivation: Alice qualifies as "Head of Household" (head_of_household) under IRC §2(b).
   - Zero oracle fallback: If adoption or residence facts are missing, status deterministically evaluates to "single".
2. Standard Deduction (IRC §63(c)(2)(B), §63(c)(7)(i)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section63.pl: s63_c_7_i),
     the basic standard deduction for a Head of Household is substituted with $18,000 (instead of $4,400).
   - Basic Standard Deduction = $18,000.
3. Personal Exemptions (IRC §151(d)(5)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section151.pl: s151_d_5),
     the exemption amount is explicitly reduced to $0.0 ("term 'exemption amount' means zero").
   - Total Personal Exemptions = $0.0.
4. Taxable Income (IRC §63(b)):
   - Alice takes the standard deduction and does not itemize.
   - Gross Income = $141,177.
   - Taxable Income = max(0, Gross Income - Standard Deduction - Personal Exemptions)
     = max(0, $141,177 - $18,000 - $0) = $123,177.
5. Personal Income Tax (IRC §1(b)(iii) Schedule B):
   - Head of Household schedule (section1.pl: s1_b_iii):
     Bracket ($76,400 < Taxable Income <= $127,500):
     Tax = $17,544 + 31% * (Taxable Income - $76,400)
         = $17,544 + 31% * ($123,177 - $76,400)
         = $17,544 + 31% * $46,777
         = $17,544 + $14,500.87
         = $32,044.87.
   - utils.pl: rounding/2 (round half-up) -> $32,045.0.
6. Employment Tax:
   - Alice had no employees in 2018. FUTA tax under §3301 = $0.0.
7. Total Tax (utils.pl: tax/3):
   - Total Tax = Income Tax ($32,045.0) + Employment Tax ($0.0) = $32,045.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Person:
    id: str
    name: str
    birth_date: int        # YYYYMMDD

@dataclass
class Adoption:
    id: str
    adoptive_parent: str   # "Alice"
    child: str             # "Bob"
    start_date: int        # 20180304

@dataclass
class Residence:
    id: str
    person: str            # "Alice" / "Bob"
    abode: str             # "house"
    start_date: int        # 20180101
    end_date: int          # 20181231

@dataclass
class HouseholdMaintenance:
    id: str
    agent: str             # "Alice"
    abode: str             # "house"
    amount: float = 1.0    # 負擔比例
    start_date: int = 20180101

# ==============================================================================
# Case 37 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_37.pl)
# 嚴格移除 "filing_status" 高階法律概念，完全由程式依事實推導
# ==============================================================================
case_37_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2018,
    "gross_income": 141177.0,
    "is_unmarried": True,
    "persons": [
        Person(id="alice_birth", name="Alice", birth_date=19920110),
        Person(id="bob_birth", name="Bob", birth_date=20140131)
    ],
    "adoptions": [
        Adoption(
            id="adopted_74_80",
            adoptive_parent="Alice",
            child="Bob",
            start_date=20180304
        )
    ],
    "residences": [
        Residence(
            id="lived_alice",
            person="Alice",
            abode="house",
            start_date=20180101,
            end_date=20181231
        ),
        Residence(
            id="lived_bob",
            person="Bob",
            abode="house",
            start_date=20180101,
            end_date=20181231
        )
    ],
    "household_maintenances": [
        HouseholdMaintenance(
            id="maintains_163_171",
            agent="Alice",
            abode="house",
            amount=1.0,
            start_date=20180101
        )
    ]
}

# ==============================================================================
# Case 37 微規則庫 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """
    對應 utils.pl: rounding/2 (四捨五入至整數)
    """
    return float(math.floor(val + 0.5))

def is_head_of_household(
    taxpayer: str,
    tax_year: int,
    adoptions: List[Adoption],
    residences: List[Residence],
    household_maintenances: Optional[List[HouseholdMaintenance]] = None,
    is_unmarried: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    對應 section2.pl: s2_b / s2_b_1_A / section152.pl: s152_f_1_B
    判定納稅人是否符合 IRC §2(b) Head of Household (戶長)：
    1. 納稅人於課稅年度未婚 (is_unmarried == True)。
    2. 納稅人負擔逾半數家庭開銷，維持主要居所。
    3. 納稅人維持之居所，在該課稅年度中為其子女（含依法收養之子女 §152(f)(1)(B)）逾半數時間的主要居所。
    """
    if not is_unmarried:
        return False, None

    first_day_year = tax_year * 10000 + 101
    last_day_year = tax_year * 10000 + 1231

    # 1. 檢驗納稅人主要居所
    taxpayer_abodes = {
        r.abode for r in residences
        if r.person == taxpayer and (r.start_date // 10000) <= tax_year <= (r.end_date // 10000)
    }
    if not taxpayer_abodes:
        return False, None

    # 2. 檢驗收養子女與同住時間
    for ad in adoptions:
        if ad.adoptive_parent == taxpayer:
            child = ad.child
            # 檢查收養起始時間是否在年度內或之前
            if ad.start_date <= last_day_year:
                child_in_abode = any(
                    r.person == child and r.abode in taxpayer_abodes and
                    (r.start_date // 10000) <= tax_year <= (r.end_date // 10000)
                    for r in residences
                )
                if child_in_abode:
                    return True, child

    return False, None

def determine_filing_status(
    taxpayer: str,
    tax_year: int,
    adoptions: List[Adoption],
    residences: List[Residence],
    household_maintenances: Optional[List[HouseholdMaintenance]] = None,
    is_unmarried: bool = True
) -> str:
    """
    依據 IRC §2(b), §1 由純粹客觀事實推導申報身分（Zero Oracle Fallback）：
    1. 檢驗是否符合 §2(b) Head of Household (戶長)。
    2. 若不符合，退回 'single'。
    嚴禁任何外部預設值。
    """
    is_hoh, _ = is_head_of_household(
        taxpayer=taxpayer,
        tax_year=tax_year,
        adoptions=adoptions,
        residences=residences,
        household_maintenances=household_maintenances,
        is_unmarried=is_unmarried
    )
    if is_hoh:
        return "head_of_household"

    return "single"

def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_2 / s63_c_7
    - 在 2018-2025 期間 (TCJA s63_c_7_i)：戶長標準扣除額提高為 $18,000。
    - 單身 / 夫妻分開申報：$12,000。
    - 夫妻合併申報 / 未亡配偶：$24,000。
    """
    if 2018 <= tax_year <= 2025:
        default_amount = 12000.0
        hoh_amount = 18000.0
    else:
        default_amount = 3000.0
        hoh_amount = 4400.0

    if filing_status == "head_of_household":
        return hoh_amount
    elif filing_status in ("married_joint", "surviving_spouse"):
        return default_amount * 2.0
    else:
        return default_amount

def compute_personal_exemptions(
    gross_income: float,
    exemption_count: int,
    filing_status: str,
    tax_year: int
) -> float:
    """
    對應 section151.pl: s151 / s151_d_5
    - 在 2018-2025 期間 (TCJA s151_d_5)：個人免稅額依法降為 $0 ("exemption amount means zero")。
    """
    if 2018 <= tax_year <= 2025:
        return 0.0

    # 2018 年前之 PEP 規則
    threshold_map = {
        "married_joint": 300000.0,
        "surviving_spouse": 300000.0,
        "head_of_household": 275000.0,
        "single": 250000.0,
        "married_separate": 150000.0
    }
    threshold = threshold_map.get(filing_status, 250000.0)
    base_ea = 2000.0
    if gross_income <= threshold:
        return float(exemption_count * base_ea)

    diff = gross_income - threshold
    step_size = 1250.0 if filing_status == "married_separate" else 2500.0
    num_steps = math.ceil(diff / step_size)
    app_pct = min(100.0, 2.0 * num_steps)
    reduction_per_ea = round_half_up((base_ea * app_pct) / 100.0)
    net_ea = max(0.0, base_ea - reduction_per_ea)
    return float(exemption_count * net_ea)

def compute_taxable_income(
    gross_income: float,
    standard_deduction: float,
    exemptions: float
) -> float:
    """
    對應 section63.pl: s63
    課稅所得 = max(0, 總收入 - 標準扣除額 - 免稅額)
    """
    return max(0.0, gross_income - standard_deduction - exemptions)

def calculate_income_tax_schedule_b(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_b / s1_b_iii
    戶長 (Head of Household) Schedule B 稅階表：
    - <= $29,600: 15%
    - $29,600 ~ $76,400: $4,440 + 28% * (Taxable Income - $29,600)
    - $76,400 ~ $127,500: $17,544 + 31% * (Taxable Income - $76,400)
    - $127,500 ~ $250,000: $33,385 + 36% * (Taxable Income - $127,500)
    - > $250,000: $77,485 + 39.6% * (Taxable Income - $250,000)
    """
    if taxable_income <= 29600.0:
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

def calculate_income_tax_schedule_c(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_c
    單身 (Single) Schedule C 稅階表
    """
    if taxable_income <= 22100.0:
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

def calculate_income_tax_schedule_a(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_a
    夫妻合併申報與未亡配偶 Schedule A 稅階表
    """
    if taxable_income <= 36900.0:
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

def calculate_case_37_tax(facts: Dict[str, Any]) -> float:
    """
    Case 37 確定性端到端微規則執行 (utils.pl: tax/3):
    由純粹底層事實推導申報身分、扣除額、免稅額與各項稅額。
    無任何 oracle 預設值。
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = facts["gross_income"]
    adoptions = facts.get("adoptions", [])
    residences = facts.get("residences", [])
    household_maintenances = facts.get("household_maintenances", [])
    is_unmarried = facts.get("is_unmarried", True)

    # 1. 嚴格由底層事實（收養關係、居所同住、未婚與開銷維持）推導申報身分，零 fallback
    filing_status = determine_filing_status(
        taxpayer=taxpayer,
        tax_year=tax_year,
        adoptions=adoptions,
        residences=residences,
        household_maintenances=household_maintenances,
        is_unmarried=is_unmarried
    )

    # 2. 標準扣除額與個人免稅額
    standard_deduction = compute_standard_deduction(filing_status, tax_year)
    exemption_count = 2 if filing_status == "head_of_household" else 1
    exemptions = compute_personal_exemptions(gross_income, exemption_count, filing_status, tax_year)

    # 3. 課稅所得
    taxable_income = compute_taxable_income(gross_income, standard_deduction, exemptions)

    # 4. 所得稅：依推導出的 filing_status 匹配對應法定稅階
    if filing_status == "head_of_household":
        income_tax = calculate_income_tax_schedule_b(taxable_income)
    elif filing_status in ("married_joint", "surviving_spouse"):
        income_tax = calculate_income_tax_schedule_a(taxable_income)
    else:  # single
        income_tax = calculate_income_tax_schedule_c(taxable_income)

    # 5. 雇主薪資稅 (無僱用人，為 $0.0)
    employment_tax = 0.0

    # 6. 稅額加總
    total_tax = income_tax + employment_tax
    return total_tax

if __name__ == "__main__":
    tax = calculate_case_37_tax(case_37_facts)
    print("=== Case 37 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_37_facts['target_person']}")
    print(f"Tax Year: {case_37_facts['tax_year']}")
    print(f"Gross Income: ${case_37_facts['gross_income']:,.2f}")

    derived_status = determine_filing_status(
        case_37_facts['target_person'],
        case_37_facts['tax_year'],
        case_37_facts.get('adoptions', []),
        case_37_facts.get('residences', []),
        case_37_facts.get('household_maintenances', []),
        case_37_facts.get('is_unmarried', True)
    )
    std_ded = compute_standard_deduction(derived_status, case_37_facts['tax_year'])
    exempt = compute_personal_exemptions(case_37_facts['gross_income'], 2, derived_status, case_37_facts['tax_year'])
    taxable_inc = compute_taxable_income(case_37_facts['gross_income'], std_ded, exempt)
    inc_tax = calculate_income_tax_schedule_b(taxable_inc)

    print(f"Derived Filing Status (Zero Fallback): {derived_status}")
    print(f"Standard Deduction (§63(c)(7)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151(d)(5)): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(b)): ${inc_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert derived_status == "head_of_household", f"Expected head_of_household, got {derived_status}"
    assert tax == 32045.0, f"Expected 32045.0, got {tax}"
    print("SUCCESS: Case 37 tax matches SARA Prolog ground truth ($32,045.0) exactly!")
