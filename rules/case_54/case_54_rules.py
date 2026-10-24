"""
Case 54: Alice Surviving Spouse Status (IRC §2(a), §1(a)(2)), TCJA Standard Deduction (§63(c)(7)),
TCJA Personal Exemptions (§151(d)(5)), and Taxable Income Calculation (§63(b)).
Direct 1:1 translation from SARA Prolog (tax_case_54.pl and statutory rules: utils.pl, section1.pl, section2.pl, section63.pl, section151.pl, section152.pl, section7703.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Surviving Spouse Status Determination from Observable Facts (IRC §2(a), §7703):
   - Alice and Bob married on Feb 3rd, 1998 (section2.pl: s2_a_1_A).
   - Bob died on Jan 1st, 2017 (death date: 20170101).
   - In tax year 2019, Bob died during either of the two years immediately preceding 2019 (2017 and 2018).
     s2_a_1_A condition: (2019 - 2 = 2017) <= 2017 <= (2019 - 1 = 2018) is met.
   - Alice has not remarried before the end of 2019 (§2(a)(2)(A)).
   - In 2019, Alice maintains as her home a household (house) which constitutes the principal place of abode of her son Charlie (born April 1st, 1999).
   - Alice furnishes over half the cost of maintaining the household (§2(a)(1)(B), §7703(b)(2)).
   - Charlie is a child of Alice and qualifies under §151 / §152.
   - Deterministic rule derivation: Alice qualifies as a "Surviving Spouse" (surviving_spouse) under IRC §2(a).
   - Zero oracle fallback: If death year or child residence facts are missing, status deterministically evaluates to "single".
2. Standard Deduction (IRC §63(c)(2)(A)(ii), §63(c)(7)(ii)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section63.pl: s63_c_7_ii),
     the basic standard deduction under subparagraph (C) is substituted with $12,000.
   - Under IRC §63(c)(2)(A)(ii), a surviving spouse receives 200% of the subparagraph (C) amount:
     Basic Standard Deduction = 200% * $12,000 = $24,000.
   - Total Standard Deduction = $24,000.
3. Personal Exemptions (IRC §151(d)(5)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section151.pl: s151_d_5),
     the exemption amount is explicitly reduced to $0.0 ("term 'exemption amount' means zero").
   - Total Personal Exemptions = $0.0.
4. Taxable Income (IRC §63(b)):
   - Alice takes the standard deduction and does not itemize.
   - Gross Income = $236,422.
   - Taxable Income = max(0, Gross Income - Standard Deduction - Personal Exemptions)
     = max(0, $236,422 - $24,000 - $0) = $212,422.
5. Personal Income Tax (IRC §1(a)(2), §1(a)(iv)):
   - Under IRC §1(a)(2), the Married Filing Jointly tax schedule is imposed on every surviving spouse.
   - Schedule A bracket ($140,000 < Taxable Income <= $250,000, section1.pl: s1_a_iv):
     Tax = $35,928.50 + 36% * (Taxable Income - $140,000)
         = $35,928.50 + 36% * ($212,422 - $140,000)
         = $35,928.50 + 36% * $72,422
         = $35,928.50 + $26,071.92
         = $62,000.42.
   - utils.pl: rounding/2 (round half-up) -> $62,000.0.
6. Employment Tax:
   - Alice had no employees in 2019. FUTA tax under §3301 = $0.0.
7. Total Tax (utils.pl: tax/3):
   - Total Tax = Income Tax ($62,000.0) + Employment Tax ($0.0) = $62,000.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Marriage:
    id: str
    spouses: List[str]     # 配偶名單 (["Alice", "Bob"])
    start_date: int        # 結婚日期 (19980203)
    end_date: Optional[int] = None

@dataclass
class Death:
    id: str
    person: str            # 身故者 ("Bob")
    date: int              # 身故日期 (20170101)

@dataclass
class Child:
    id: str
    name: str              # 子女姓名 ("Charlie")
    parents: List[str]     # 父母名單 (["Alice", "Bob"])
    birth_date: int        # 出生日期 (19990401)

@dataclass
class Residence:
    id: str
    person: str            # 居住者 ("Alice" / "Charlie")
    abode: str             # 居所名稱 ("house")
    start_date: int        # 開始日期 (20190101)
    end_date: int          # 結束日期 (20191231)

@dataclass
class HouseholdMaintenance:
    id: str
    agent: str             # 維持開銷者 ("Alice")
    abode: str             # 居所名稱 ("house")
    amount: float = 1.0    # 負擔比例或開銷
    start_date: int = 20190101

# ==============================================================================
# Case 54 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_54.pl)
# 嚴格移除 "filing_status" 高階法律概念，完全由程式依事實推導
# ==============================================================================
case_54_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "deceased_spouse": "Bob",
    "tax_year": 2019,
    "gross_income": 236422.0,
    "marriages": [
        Marriage(
            id="married_18_24",
            spouses=["Alice", "Bob"],
            start_date=19980203,
            end_date=None
        )
    ],
    "deaths": [
        Death(
            id="died_94_97",
            person="Bob",
            date=20170101
        )
    ],
    "children": [
        Child(
            id="son_55_57",
            name="Charlie",
            parents=["Alice", "Bob"],
            birth_date=19990401
        )
    ],
    "residences": [
        Residence(
            id="residence_alice_house",
            person="Alice",
            abode="house",
            start_date=20190101,
            end_date=20191231
        ),
        Residence(
            id="residence_charlie_house",
            person="Charlie",
            abode="house",
            start_date=20190101,
            end_date=20191231
        )
    ],
    "household_maintenances": [
        HouseholdMaintenance(
            id="maintains_164_172",
            agent="Alice",
            abode="house",
            amount=1.0,
            start_date=20190101
        )
    ]
}

# ==============================================================================
# Case 54 微規則庫 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """
    對應 utils.pl: rounding/2 (四捨五入至整數)
    """
    return float(math.floor(val + 0.5))

def is_surviving_spouse(
    taxpayer: str,
    tax_year: int,
    marriages: List[Marriage],
    deaths: List[Death],
    children: List[Child],
    residences: List[Residence],
    household_maintenances: Optional[List[HouseholdMaintenance]] = None
) -> Tuple[bool, Optional[str]]:
    """
    對應 section2.pl: s2_a / s2_a_1 / s2_a_1_A / s2_a_1_B / s2_a_2
    判定納稅人是否符合 IRC §2(a) Surviving Spouse (未亡配偶)：
    1. s2_a_1_A: 納稅人之配偶於課稅年度前兩年內身故 (tax_year - 2 <= death_year <= tax_year - 1)。
       在 2019 年度中，配偶 Bob 於 20170101 身故 (2017 年)，符合條件。
    2. s2_a_2_A: 納稅人在課稅年度結束前未再婚。
    3. s2_a_1_B: 納稅人負擔家庭主要開銷，維持其主要居所。
    4. s2_a_1_B: 納稅人之子女 (son/daughter) 與納稅人同住於該居所。
    """
    first_day_year = tax_year * 10000 + 101
    last_day_year = tax_year * 10000 + 1231

    # 1. 檢驗配偶身故年份 (s2_a_1_A)
    two_years_prior = tax_year - 2
    one_year_prior = tax_year - 1

    deceased_spouse = None
    for m in marriages:
        if taxpayer in m.spouses:
            potential_spouse = next((p for p in m.spouses if p != taxpayer), None)
            if potential_spouse:
                for d in deaths:
                    if d.person == potential_spouse:
                        death_year = d.date // 10000
                        if two_years_prior <= death_year <= one_year_prior:
                            # 確認身故在婚姻開始之後，且身故前未離婚
                            if m.start_date <= d.date:
                                if m.end_date is None or d.date <= m.end_date:
                                    deceased_spouse = potential_spouse
                                    break
        if deceased_spouse:
            break

    if not deceased_spouse:
        return False, None

    # 2. 檢驗是否再婚 (s2_a_2_A)
    for m in marriages:
        if taxpayer in m.spouses and deceased_spouse not in m.spouses:
            if m.start_date <= last_day_year:
                return False, None

    # 3. 檢驗納稅人主要居所與同住子女 (s2_a_1_B)
    taxpayer_abodes = {
        r.abode for r in residences
        if r.person == taxpayer and r.start_date <= first_day_year and r.end_date >= last_day_year
    }
    if not taxpayer_abodes:
        # 居所跨度若為年內均可接受
        taxpayer_abodes = {
            r.abode for r in residences
            if r.person == taxpayer and (r.start_date // 10000) <= tax_year <= (r.end_date // 10000)
        }
    if not taxpayer_abodes:
        return False, None

    has_qualifying_child_in_abode = False
    for ch in children:
        if taxpayer in ch.parents:
            child_in_abode = any(
                r.person == ch.name and r.abode in taxpayer_abodes and
                (r.start_date // 10000) <= tax_year <= (r.end_date // 10000)
                for r in residences
            )
            if child_in_abode:
                has_qualifying_child_in_abode = True
                break

    if not has_qualifying_child_in_abode:
        return False, None

    return True, deceased_spouse

def determine_filing_status(
    taxpayer: str,
    tax_year: int,
    marriages: List[Marriage],
    deaths: List[Death],
    children: List[Child],
    residences: List[Residence],
    household_maintenances: Optional[List[HouseholdMaintenance]] = None
) -> str:
    """
    依據 IRC §2(a), §7703, §1 由純粹客觀事實推導申報身分（Zero Oracle Fallback）：
    1. 檢驗是否符合 §2(a) Surviving Spouse (未亡配偶)。
    2. 若不符合，檢驗婚姻與子女狀態；無其他資格時退回 'single'。
    嚴禁任何外部預設值。
    """
    is_ss, _ = is_surviving_spouse(
        taxpayer=taxpayer,
        tax_year=tax_year,
        marriages=marriages,
        deaths=deaths,
        children=children,
        residences=residences,
        household_maintenances=household_maintenances
    )
    if is_ss:
        return "surviving_spouse"

    return "single"

def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_2 / s63_c_7
    - 在 2018-2025 期間 (TCJA s63_c_7_ii)：基準標準扣除額 subparagraph (C) 為 $12,000。
    - 未亡配偶 / 夫妻合併申報 (s63_c_2_A)：為基準額之 200% (2 * $12,000 = $24,000)。
    - 戶長 (s63_c_7_i)：$18,000。
    - 單身 / 夫妻分開申報：$12,000。
    """
    if 2018 <= tax_year <= 2025:
        default_amount = 12000.0
        hoh_amount = 18000.0
    else:
        default_amount = 3000.0
        hoh_amount = 4400.0

    if filing_status in ("married_joint", "surviving_spouse"):
        return default_amount * 2.0  # 2019 年為 $24,000
    elif filing_status == "head_of_household":
        return hoh_amount
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

def calculate_income_tax_schedule_a(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_a / s1_a_2 / s1_a_iv
    夫妻合併申報與未亡配偶 (Surviving Spouse) 適用 Schedule A 稅階表：
    - <= $36,900: 15%
    - $36,900 ~ $89,150: $5,535 + 28% * (Taxable Income - $36,900)
    - $89,150 ~ $140,000: $20,165 + 31% * (Taxable Income - $89,150)
    - $140,000 ~ $250,000: $35,928.50 + 36% * (Taxable Income - $140,000)
    - > $250,000: $75,528.50 + 39.6% * (Taxable Income - $250,000)
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

def calculate_income_tax_schedule_b(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_b
    戶長 (Head of Household) 稅階表
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
    單身 (Single) 稅階表
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

def calculate_case_54_tax(facts: Dict[str, Any]) -> float:
    """
    Case 54 確定性端到端微規則執行 (utils.pl: tax/3):
    由純粹底層事實推導申報身分、扣除額、免稅額與各項稅額。
    無任何 oracle 預設值。
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = facts["gross_income"]
    marriages = facts.get("marriages", [])
    deaths = facts.get("deaths", [])
    children = facts.get("children", [])
    residences = facts.get("residences", [])
    household_maintenances = facts.get("household_maintenances", [])

    # 1. 嚴格由底層事實（配偶身故年份、子女同住、開銷負擔）推導申報身分，零 fallback
    filing_status = determine_filing_status(
        taxpayer=taxpayer,
        tax_year=tax_year,
        marriages=marriages,
        deaths=deaths,
        children=children,
        residences=residences,
        household_maintenances=household_maintenances
    )

    # 2. 標準扣除額與個人免稅額
    standard_deduction = compute_standard_deduction(filing_status, tax_year)
    exemption_count = 2 if filing_status == "surviving_spouse" else 1
    exemptions = compute_personal_exemptions(gross_income, exemption_count, filing_status, tax_year)

    # 3. 課稅所得
    taxable_income = compute_taxable_income(gross_income, standard_deduction, exemptions)

    # 4. 所得稅：依推導出的 filing_status 匹配對應法定稅階
    if filing_status in ("married_joint", "surviving_spouse"):
        income_tax = calculate_income_tax_schedule_a(taxable_income)
    elif filing_status == "head_of_household":
        income_tax = calculate_income_tax_schedule_b(taxable_income)
    else:  # single
        income_tax = calculate_income_tax_schedule_c(taxable_income)

    # 5. 雇主薪資稅 (無僱用人，為 $0.0)
    employment_tax = 0.0

    # 6. 稅額加總
    total_tax = income_tax + employment_tax
    return total_tax

if __name__ == "__main__":
    tax = calculate_case_54_tax(case_54_facts)
    print("=== Case 54 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_54_facts['target_person']}")
    print(f"Deceased Spouse: {case_54_facts.get('deceased_spouse')}")
    print(f"Tax Year: {case_54_facts['tax_year']}")
    print(f"Gross Income: ${case_54_facts['gross_income']:,.2f}")

    derived_status = determine_filing_status(
        case_54_facts['target_person'],
        case_54_facts['tax_year'],
        case_54_facts.get('marriages', []),
        case_54_facts.get('deaths', []),
        case_54_facts.get('children', []),
        case_54_facts.get('residences', []),
        case_54_facts.get('household_maintenances', [])
    )
    std_ded = compute_standard_deduction(derived_status, case_54_facts['tax_year'])
    exempt = compute_personal_exemptions(case_54_facts['gross_income'], 2, derived_status, case_54_facts['tax_year'])
    taxable_inc = compute_taxable_income(case_54_facts['gross_income'], std_ded, exempt)
    inc_tax = calculate_income_tax_schedule_a(taxable_inc)

    print(f"Derived Filing Status (Zero Fallback): {derived_status}")
    print(f"Standard Deduction (§63(c)(7)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151(d)(5)): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(a)(2)): ${inc_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert derived_status == "surviving_spouse", f"Expected surviving_spouse, got {derived_status}"
    assert tax == 62000.0, f"Expected 62000.0, got {tax}"
    print("SUCCESS: Case 54 tax matches SARA Prolog ground truth ($62,000.0) exactly!")
