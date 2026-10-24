"""
Case 51: Alice Head of Household (§2(b)), Standard Deduction (§63(c)), Personal Exemptions (§151),
and SARA Agricultural Labor FUTA Rules (§3301, §3306(a)(2), §3306(b)(1), §3306(c)(1)).
Direct 1:1 translation from SARA Prolog (tax_case_51.pl and statutory rules: utils.pl, section1.pl, section2.pl, section63.pl, section151.pl, section152.pl, section3301.pl, section3306.pl, section7703.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Head of Household Status (IRC §2(b), §151, §152, §7703):
   - In 2017, Alice is unmarried and maintains as her principal place of abode a house where her mother Dorothy lives.
   - Alice furnishes over 50% of the household maintenance costs.
   - Dorothy has no income and receives full support from Alice, qualifying as a qualifying relative under §152(d)(2)(C).
   - Under IRC §2(b)(1)(B), maintaining a household that is the principal place of abode of the taxpayer's mother
     entitles Alice to the "Head of Household" filing status.
2. Standard Deduction (IRC §63(c)(2)(B)):
   - Basic standard deduction for Head of Household in 2017 = $4,400.
3. Personal Exemptions & PEP Phaseout (IRC §151, §152, §151(d)(3)):
   - Entitled to 2 exemptions: Alice (taxpayer) + Dorothy (mother) = 2 * $2,000 = $4,000.
   - Head of Household PEP threshold = $275,000.
   - Gross Income ($197,407) < $275,000 -> 0% phaseout -> allowable exemptions = $4,000.
4. Taxable Income & Personal Income Tax (IRC §1(b)(iv)):
   - Taxable Income = max(0, $197,407 - $4,400 - $4,000) = $189,007.
   - Head of Household bracket ($127,500 < Taxable Income <= $250,000):
     Tax = $33,385 + 36% * ($189,007 - $127,500)
         = $33,385 + 36% * $61,507
         = $33,385 + $22,142.52
         = $55,527.52.
   - Round half-up -> $55,528.0.
5. Employment Tax (FUTA IRC §3301 / §3306 under SARA Prolog formalization):
   - Alice paid Bob $23,200 for agricultural labor in Caracas, Venezuela.
   - Under SARA's section3306.pl (s3306_a_2_A):
     An employer is an agricultural employer if the sum of employee wages (where each employee's wage
     is capped at $7,000 under s3306_b / §3306(b)(1)) is $20,000 or more.
   - Because Alice only employed Bob, Bob's capped wage under s3306_b is min($23,200, $7,000) = $7,000.
   - Since $7,000 < $20,000, Alice does not meet the $20,000 threshold under s3306_a_2_A.
   - Under s3306_a_2_B, Alice did not employ 5 or more individuals.
   - Therefore, under SARA Prolog, Alice is NOT an employer under §3306(a), and FUTA tax under §3301 = $0.0.
6. Total Tax (utils.pl: tax/3):
   - Total Tax = Income Tax ($55,528.0) + Employment Tax ($0.0) = $55,528.0.
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
    means: str = "cash"

@dataclass
class Service:
    id: str
    agent: str             # 勞務提供者
    patient: str           # 勞務接受者
    purpose: str           # e.g. "agricultural labor"
    start_date: int        # 開始日期 (YYYYMMDD)
    end_date: int          # 結束日期 (YYYYMMDD)
    location: Optional[str] = None
    country: Optional[str] = None

@dataclass
class Dependent:
    id: str
    name: str
    relationship: str      # e.g. "mother", "father"
    gross_income: float = 0.0
    support_ratio_by_taxpayer: float = 1.0

@dataclass
class Residence:
    person: str
    abode: str
    start_date: int        # YYYYMMDD
    end_date: int          # YYYYMMDD

# ==============================================================================
# Case 51 原始事實 (Facts - 1:1 映射 Prolog tax_case_51.pl)
# ==============================================================================
case_51_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "tax_year": 2017,
    "gross_income": 197407.0,
    "filing_status": "head_of_household",
    "is_unmarried": True,
    "household_furnish_ratio": 1.0,
    "payments": [
        Payment(
            id="paid_10_13",
            agent="Alice",
            patient="Bob",
            amount=23200.0,
            start_date=20170902,
            purpose="labor",
            means="cash"
        )
    ],
    "services": [
        Service(
            id="labor_62_66",
            agent="Bob",
            patient="Alice",
            purpose="agricultural labor",
            start_date=20170201,
            end_date=20170902,
            location="Caracas, Venezuela",
            country="Venezuela"
        )
    ],
    "dependents": [
        Dependent(
            id="mother_267_272",
            name="Dorothy",
            relationship="mother",
            gross_income=0.0,
            support_ratio_by_taxpayer=1.0
        )
    ],
    "residences": [
        Residence(
            person="Alice",
            abode="house",
            start_date=20170101,
            end_date=20171231
        ),
        Residence(
            person="Dorothy",
            abode="house",
            start_date=20170101,
            end_date=20171231
        )
    ]
}

# ==============================================================================
# Case 51 微規則 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """
    對應 utils.pl: rounding/2 (四捨五入至整數)
    """
    return float(math.floor(val + 0.5))

def is_qualifying_relative(
    dependent: Dependent,
    taxpayer: str,
    tax_year: int
) -> bool:
    """
    對應 section152.pl: s152(Dependent, Taxpayer, TaxYear)
    直系尊親屬（母親）、所得未達免稅額、納稅人負擔過半生活費。
    """
    eligible_relationships = {"mother", "father", "son", "daughter", "brother", "sister"}
    if dependent.relationship not in eligible_relationships:
        return False
    if dependent.gross_income >= 4050.0:
        return False
    if dependent.support_ratio_by_taxpayer <= 0.5:
        return False
    return True

def is_head_of_household(
    taxpayer: str,
    dependents: List[Dependent],
    residences: List[Residence],
    tax_year: int,
    is_unmarried: bool = True,
    household_furnish_ratio: float = 1.0
) -> bool:
    """
    對應 section2.pl: s2_b_1_B / s2_b
    納稅人未婚、負擔逾半數家庭開銷，且與符合 §152 撫養資格之母親居住於同一主要居所（Residence）。
    """
    if not is_unmarried or household_furnish_ratio <= 0.5:
        return False

    taxpayer_abodes = {
        r.abode for r in residences
        if r.person == taxpayer and (r.start_date // 10000) <= tax_year <= (r.end_date // 10000)
    }
    if not taxpayer_abodes:
        return False

    for d in dependents:
        if d.relationship in ("mother", "father") and is_qualifying_relative(d, taxpayer, tax_year):
            parent_in_abode = any(
                r.person == d.name and r.abode in taxpayer_abodes and
                (r.start_date // 10000) <= tax_year <= (r.end_date // 10000)
                for r in residences
            )
            if parent_in_abode:
                return True

    return False

def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_2_B
    2017 戶長標準扣除額為 $4,400。
    """
    if filing_status == "head_of_household":
        return 4400.0
    elif filing_status in ("married_joint", "surviving_spouse"):
        return 6000.0
    else:
        return 3000.0

def compute_pep_exemptions(
    gross_income: float,
    exemption_count: int,
    filing_status: str,
    tax_year: int
) -> float:
    """
    對應 section151.pl: s151 / s151_d_3 (PEP)
    每人基準 $2,000。戶長門檻 $275,000。
    """
    threshold = 275000.0 if filing_status == "head_of_household" else 250000.0
    base_ea = 2000.0
    if gross_income <= threshold:
        return float(exemption_count * base_ea)

    diff = gross_income - threshold
    num_steps = math.ceil(diff / 2500.0)
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
    對應 section1.pl: s1_b / s1_b_iv
    戶長稅階（$127,500 ~ $250,000）：
    Tax = 33,385 + 36% * (Taxable Income - 127,500)
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

def is_sara_agricultural_employer(
    taxpayer: str,
    payments: List[Payment],
    services: List[Service],
    tax_year: int
) -> Tuple[bool, float]:
    """
    對應 SARA section3306.pl: s3306_a_2 / s3306_a_2_A / s3306_a_2_B
    SARA Prolog 實作邏輯：
    1. s3306_a_2_A 呼叫 s3306_a_2_is_wages，其內部呼叫 s3306_b (每位員工工資先受 $7,000 上限限制)。
    2. 加總所有員工受限後的工資 Wageslist，檢查總和 Wages >= 20000。
    3. s3306_a_2_B 檢查員工數是否 >= 5 人。
    在 Case 51 中：Alice 僅聘用 Bob 1 人，受限後工資 min(23200, 7000) = $7,000 < $20,000，且人數 < 5，
    因此判定 Alice 非農業雇主。
    """
    wages_by_employee: Dict[str, float] = {}

    for p in payments:
        if p.agent == taxpayer:
            is_ag = any(
                s.patient == taxpayer and s.agent == p.patient and "agricultural" in s.purpose.lower()
                for s in services
            )
            if not is_ag and p.purpose and "agricultural" in p.purpose.lower():
                is_ag = True

            if is_ag:
                pyear = p.start_date // 10000
                if pyear == tax_year:
                    wages_by_employee[p.patient] = wages_by_employee.get(p.patient, 0.0) + p.amount

    # SARA Prolog 規則：先套用 s3306_b 之 $7,000 上限
    capped_wages = {emp: min(7000.0, wage) for emp, wage in wages_by_employee.items()}
    total_capped_wages = sum(capped_wages.values())

    # s3306_a_2_A 檢查 capped 總額 >= 20000
    is_ag_employer_A = total_capped_wages >= 20000.0
    # s3306_a_2_B 檢查受僱人數 >= 5
    is_ag_employer_B = len(wages_by_employee) >= 5

    is_employer = is_ag_employer_A or is_ag_employer_B
    return is_employer, total_capped_wages

def calculate_agricultural_futa_tax(
    taxpayer: str,
    payments: List[Payment],
    services: List[Service],
    tax_year: int
) -> float:
    """
    對應 SARA section3301.pl: s3301
    若具備雇主身分，課徵 6% 稅率；若不具備雇主身分，稅額為 $0.0。
    """
    is_employer, capped_wages = is_sara_agricultural_employer(taxpayer, payments, services, tax_year)
    if not is_employer:
        return 0.0
    return round_half_up(capped_wages * 0.06)

def calculate_case_51_tax(facts: Dict[str, Any]) -> float:
    """
    Case 51 確定性端到端微規則執行 (utils.pl: tax/3):
    Total Tax = 所得稅(§1) + 雇主失業稅(§3301)
    """
    taxpayer = facts["target_person"]
    tax_year = facts["tax_year"]
    gross_income = facts["gross_income"]
    dependents = facts.get("dependents", [])
    residences = facts.get("residences", [])
    payments = facts.get("payments", [])
    services = facts.get("services", [])
    is_unmarried = facts.get("is_unmarried", True)
    household_furnish_ratio = facts.get("household_furnish_ratio", 1.0)

    # 1. 判斷申報身分 (IRC §2(b) 戶長，查驗 Residence、費用負擔、Qualifying Relative)
    hoh = is_head_of_household(
        taxpayer=taxpayer,
        dependents=dependents,
        residences=residences,
        tax_year=tax_year,
        is_unmarried=is_unmarried,
        household_furnish_ratio=household_furnish_ratio
    )
    filing_status = "head_of_household" if hoh else facts.get("filing_status", "single")

    # 2. 標準扣除額與個人免稅額
    standard_deduction = compute_standard_deduction(filing_status, tax_year)
    exemption_count = 1 + len(dependents)  # Alice + Dorothy = 2
    exemptions = compute_pep_exemptions(gross_income, exemption_count, filing_status, tax_year)

    # 3. 課稅所得與個人所得稅 (IRC §1(b))
    taxable_income = compute_taxable_income(gross_income, standard_deduction, exemptions)
    income_tax = calculate_income_tax_schedule_b(taxable_income)

    # 4. 農業雇主薪資稅 (SARA §3301 / §3306)
    employment_tax = calculate_agricultural_futa_tax(taxpayer, payments, services, tax_year)

    # 5. 稅額加總
    total_tax = income_tax + employment_tax
    return total_tax

if __name__ == "__main__":
    tax = calculate_case_51_tax(case_51_facts)
    print(f"=== Case 51 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_51_facts['target_person']}")
    print(f"Tax Year: {case_51_facts['tax_year']}")
    print(f"Gross Income: ${case_51_facts['gross_income']:,.2f}")

    hoh = is_head_of_household(
        case_51_facts['target_person'],
        case_51_facts['dependents'],
        case_51_facts['residences'],
        case_51_facts['tax_year'],
        is_unmarried=case_51_facts['is_unmarried'],
        household_furnish_ratio=case_51_facts['household_furnish_ratio']
    )
    status = "head_of_household" if hoh else "single"
    std_ded = compute_standard_deduction(status, case_51_facts['tax_year'])
    exempt = compute_pep_exemptions(case_51_facts['gross_income'], 2, status, case_51_facts['tax_year'])
    taxable_inc = compute_taxable_income(case_51_facts['gross_income'], std_ded, exempt)
    inc_tax = calculate_income_tax_schedule_b(taxable_inc)
    emp_tax = calculate_agricultural_futa_tax(
        case_51_facts['target_person'],
        case_51_facts['payments'],
        case_51_facts['services'],
        case_51_facts['tax_year']
    )

    print(f"Filing Status: {status}")
    print(f"Standard Deduction (§63): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(b)): ${inc_tax:,.2f}")
    print(f"Employment Tax (§3301 FUTA): ${emp_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert tax == 55528.0, f"Expected 55528.0, got {tax}"
    print("SUCCESS: Case 51 tax matches SARA Prolog ground truth ($55,528.0) exactly!")
