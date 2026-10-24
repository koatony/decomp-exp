"""
Case 46: Alice Married Filing Jointly (§1(a), §7703), TCJA Standard Deduction (§63(c)(7)),
TCJA Personal Exemptions (§151(d)(5)), and Agricultural Labor FUTA Rules (§3301, §3306(a)(2), §3306(b)(11)).
Direct 1:1 translation from SARA Prolog (tax_case_46.pl and statutory rules: utils.pl, section1.pl, section63.pl, section151.pl, section3301.pl, section3306.pl, section7703.pl).

Statutory Walkthrough (SARA Benchmark Specification):
1. Filing Status Determination from Observable Facts (IRC §7703, §1(a)(1), §1(c), §1(d)):
   - Observable facts: Alice has been married to spouse since 1999 (section7703.pl: s7703).
   - Observable facts: Alice and spouse filed a joint return for 2020 (section1.pl: s1_a_1).
   - Deterministic rule derivation: Valid marriage + Joint Return -> Filing Status = "Married Filing Jointly" (married_joint).
   - Zero oracle fallback: If marriage or joint return is absent, status deterministically evaluates to "single" or "married_separate".
2. Standard Deduction (IRC §63(c)(2)(A), §63(c)(7)(ii)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section63.pl: s63_c_7_ii),
     the basic standard deduction under subparagraph (C) is substituted with $12,000 (instead of $3,000).
   - Under §63(c)(2)(A), married individuals filing a joint return receive 200% of the subparagraph (C) amount:
     Basic Standard Deduction = 200% * $12,000 = $24,000.
   - Neither spouse is aged or blind, so additional standard deduction is $0.
   - Total Standard Deduction = $24,000.
3. Personal Exemptions (IRC §151(d)(5)):
   - Under TCJA special rules for taxable years 2018 through 2025 (section151.pl: s151_d_5),
     the exemption amount is explicitly reduced to $0.0 ("term 'exemption amount' means zero").
   - Total Personal Exemptions = $0.0.
4. Taxable Income (IRC §63(b)):
   - Alice takes the standard deduction and does not itemize.
   - Gross Income = $103,272.
   - Taxable Income = max(0, Gross Income - Standard Deduction - Personal Exemptions)
     = max(0, $103,272 - $24,000 - $0) = $79,272.
5. Personal Income Tax (IRC §1(a)(ii)):
   - Schedule A (Married Individuals Filing Joint Returns, section1.pl: s1_a_ii):
     Bracket ($36,900 < Taxable Income <= $89,150):
     Tax = $5,535 + 28% * (Taxable Income - $36,900)
         = $5,535 + 28% * ($79,272 - $36,900)
         = $5,535 + 28% * $42,372
         = $5,535 + $11,864.16
         = $17,399.16.
   - utils.pl: rounding/2 (round half-up) -> $17,399.0.
6. Employment Tax (FUTA IRC §3301 / §3306(a)(2) / §3306(b)(11)):
   - Alice paid Bob $3,200 for agricultural labor done in 2020.
   - Alice paid Bob with "eggs, grapes and hay" (non-cash medium).
   - Under IRC §3306(b)(11) (section3306.pl: s3306_b_11), remuneration for agricultural labor paid
     in any medium other than cash is expressly excluded from the statutory definition of "wages".
   - Moreover, even if it were cash, total remuneration ($3,200) < $20,000 agricultural employer threshold
     under §3306(a)(2)(A), and Alice employed only 1 individual (< 5 individuals under §3306(a)(2)(B)).
   - Therefore, under SARA Prolog, Alice is NOT an employer under §3306(a), and FUTA tax under §3301 = $0.0.
7. Total Tax (utils.pl: tax/3):
   - Total Tax = Income Tax ($17,399.0) + Employment Tax ($0.0) = $17,399.0.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import math

@dataclass
class Payment:
    id: str
    agent: Optional[str]   # 付款人 (Alice)
    patient: str           # 收款人 (Bob)
    amount: float          # 金額 ($3,200)
    start_date: int        # 日期 (YYYYMMDD, e.g. 20200902)
    purpose: Optional[str] = None
    means: str = "cash"    # 支付媒介 (e.g. "eggs, grapes and hay")

@dataclass
class Service:
    id: str
    agent: str             # 勞務提供者 (Bob)
    patient: str           # 勞務接受者 (Alice)
    purpose: str           # e.g. "agricultural labor"
    start_date: int        # 開始日期 (YYYYMMDD, e.g. 20200201)
    end_date: int          # 結束日期 (YYYYMMDD, e.g. 20200902)
    location: Optional[str] = None
    country: Optional[str] = None

@dataclass
class Marriage:
    id: str
    spouses: List[str]     # 配偶名單 (["Alice", "spouse"])
    start_date: int        # 結婚日期 (19990101)
    end_date: Optional[int] = None

@dataclass
class JointReturn:
    id: str
    spouses: List[str]     # 申報配偶 (["Alice", "spouse"])
    start_date: int        # 申報日期 (20200101)
    tax_year: int          # 申報年度 (2020)

# ==============================================================================
# Case 46 純粹可觀察事實 (Observable Facts - 1:1 映射 Prolog tax_case_46.pl)
# 嚴格移除 "filing_status" 高階法律概念，完全由程式依事實推導
# ==============================================================================
case_46_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "spouse": "spouse",
    "tax_year": 2020,
    "gross_income": 103272.0,
    "marriages": [
        Marriage(
            id="married_150_156",
            spouses=["Alice", "spouse"],
            start_date=19990101,
            end_date=None
        )
    ],
    "joint_returns": [
        JointReturn(
            id="joint_return_184_195",
            spouses=["Alice", "spouse"],
            start_date=20200101,
            tax_year=2020
        )
    ],
    "payments": [
        Payment(
            id="paid_10_13",
            agent="Alice",
            patient="Bob",
            amount=3200.0,
            start_date=20200902,
            purpose="labor",
            means="eggs, grapes and hay"
        )
    ],
    "services": [
        Service(
            id="labor_45_49",
            agent="Bob",
            patient="Alice",
            purpose="agricultural labor",
            start_date=20200201,
            end_date=20200902
        )
    ]
}

# ==============================================================================
# Case 46 微規則庫 (SARA Prolog 1:1 Micro-Rules)
# ==============================================================================

def round_half_up(val: float) -> float:
    """
    對應 utils.pl: rounding/2 (四捨五入至整數)
    """
    return float(math.floor(val + 0.5))

def is_valid_marriage(
    taxpayer: str,
    spouse: Optional[str],
    tax_year: int,
    marriages: List[Marriage]
) -> Tuple[bool, Optional[str]]:
    """
    對應 section7703.pl: s7703
    判定在稅務年度結束前是否具備合法婚姻關係，且該年度內未終止。
    若未指定 spouse，亦會自動檢視 marriages 中與 taxpayer 締結婚姻的配偶。
    """
    first_day = tax_year * 10000 + 101
    last_day = tax_year * 10000 + 1231
    for m in marriages:
        if taxpayer in m.spouses:
            # 尋找配偶姓名
            partner = spouse if (spouse and spouse in m.spouses) else next((p for p in m.spouses if p != taxpayer), None)
            if partner:
                if m.start_date <= last_day:
                    if m.end_date is None or m.end_date >= first_day:
                        return True, partner
    return False, None

def is_joint_return(
    taxpayer: str,
    spouse: Optional[str],
    tax_year: int,
    joint_returns: List[JointReturn],
    marriages: List[Marriage]
) -> bool:
    """
    對應 section1.pl: s1_a_1 / section63.pl: s63_c_2_A_i
    夫妻符合 §7703 婚姻要件，且於該稅務年度共同提出聯合申報表。
    """
    is_m, confirmed_spouse = is_valid_marriage(taxpayer, spouse, tax_year, marriages)
    if not is_m or not confirmed_spouse:
        return False

    for jr in joint_returns:
        if taxpayer in jr.spouses and confirmed_spouse in jr.spouses:
            jr_year = jr.start_date // 10000 if jr.start_date else jr.tax_year
            if jr_year == tax_year or jr.tax_year == tax_year:
                return True
    return False

def determine_filing_status(
    taxpayer: str,
    tax_year: int,
    marriages: List[Marriage],
    joint_returns: List[JointReturn],
    spouse: Optional[str] = None
) -> str:
    """
    依據 IRC §7703, §1(a), §1(c), §1(d) 由純粹底層事實推導申報身分（Zero Oracle Fallback）：
    1. 判定是否有合法有效之婚姻關係 (IRC §7703)。
    2. 若具備婚姻：
       - 若雙方在該稅務年度提出共同申報 (Joint Return)，則判定為 'married_joint' (IRC §1(a)(1))。
       - 若未共同申報，則判定為 'married_separate' (IRC §1(d))。
    3. 若無有效婚姻關係：
       - 判定為 'single' (IRC §1(c))。
    嚴禁任何外部預設值或 fallback 默認。
    """
    is_m, confirmed_spouse = is_valid_marriage(taxpayer, spouse, tax_year, marriages)
    if is_m and confirmed_spouse:
        if is_joint_return(taxpayer, confirmed_spouse, tax_year, joint_returns, marriages):
            return "married_joint"
        return "married_separate"
    return "single"

def compute_standard_deduction(filing_status: str, tax_year: int) -> float:
    """
    對應 section63.pl: s63_c_2 / s63_c_7
    - 在 2018-2025 期間 (TCJA s63_c_7_ii)：基準標準扣除額 subparagraph (C) 提高為 $12,000。
    - 夫妻合併申報 (s63_c_2_A)：為基準額之 200% (2 * $12,000 = $24,000)。
    - 戶長 (s63_c_7_i)：$18,000。
    - 單身 / 夫妻分開申報：$12,000。
    - 在 2018 年以前：
      * 夫妻合併申報：2 * $3,000 = $6,000。
      * 戶長：$4,400。
      * 單身：$3,000。
    """
    if 2018 <= tax_year <= 2025:
        default_amount = 12000.0
        hoh_amount = 18000.0
    else:
        default_amount = 3000.0
        hoh_amount = 4400.0

    if filing_status in ("married_joint", "surviving_spouse"):
        return default_amount * 2.0  # 2020 年為 $24,000
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
    - 在 2018 年以前：每人基準 $2,000，並依 IRC §151(d)(3) 及 §68(b) 門檻進行 PEP 逐步遞減。
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
    對應 section1.pl: s1_a / s1_a_ii
    夫妻合併申報 (Married Filing Jointly) 稅階表
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
    對應 section1.pl: s1_b / s1_b_ii
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
    對應 section1.pl: s1_c / s1_c_iii
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

def calculate_income_tax_schedule_d(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_d
    夫妻分開申報 (Married Filing Separately) 稅階表
    """
    if taxable_income <= 18450.0:
        tax = taxable_income * 0.15
    elif taxable_income <= 44575.0:
        tax = 2767.50 + (taxable_income - 18450.0) * 0.28
    elif taxable_income <= 70000.0:
        tax = 10082.50 + (taxable_income - 44575.0) * 0.31
    elif taxable_income <= 125000.0:
        tax = 17964.25 + (taxable_income - 70000.0) * 0.36
    else:
        tax = 37764.25 + (taxable_income - 125000.0) * 0.396

    return round_half_up(tax)

def is_sara_agricultural_employer(
    taxpayer: str,
    payments: List[Payment],
    services: List[Service],
    tax_year: int
) -> Tuple[bool, float]:
    """
    對應 SARA section3306.pl: s3306_a_2 / s3306_a_2_A / s3306_a_2_B / s3306_b / s3306_b_11
    SARA Prolog 實作邏輯：
    1. s3306_b 規定工資（wages）定義。
    2. s3306_b_11 明確排除以非現金媒介（medium other than cash，如雞蛋、葡萄、乾草）支付之農業勞務報酬。
       若以非現金支付農業勞工，則該筆款項不計入 FUTA 工資（wages = 0）。
    3. 即使為現金支付，s3306_a_2_A 規定該曆季或前一曆年農業勞務工資須累計滿 $20,000（且每人上限 $7,000）。
    4. s3306_a_2_B 檢查受僱農業勞工人數是否達 5 人以上。
    在 Case 46 中：Alice 以非現金物品支付 Bob $3,200，符合 §3306(b)(11) 排除條款，
    且金額未達 $20,000、人數僅 1 人，故判定 Alice 非農業雇主。
    """
    wages_by_employee: Dict[str, float] = {}

    for p in payments:
        if p.agent == taxpayer:
            # 檢查勞務關聯與用途
            is_ag = any(
                s.patient == taxpayer and s.agent == p.patient and "agricultural" in s.purpose.lower()
                for s in services
            )
            if not is_ag and p.purpose and "agricultural" in p.purpose.lower():
                is_ag = True

            if is_ag:
                pyear = p.start_date // 10000
                if pyear == tax_year:
                    # s3306_b_11: 非現金支付農業勞務排除於 wages 之外
                    means_clean = (p.means or "").strip().lower()
                    if means_clean and means_clean != "cash":
                        continue  # 不計入工資

                    wages_by_employee[p.patient] = wages_by_employee.get(p.patient, 0.0) + p.amount

    # s3306_b_1: 每位員工受限於 $7,000 上限
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
    若具備雇主身分，課徵 6% 稅率；若不具備雇主身分，失業稅額為 $0.0。
    """
    is_employer, capped_wages = is_sara_agricultural_employer(taxpayer, payments, services, tax_year)
    if not is_employer:
        return 0.0
    return round_half_up(capped_wages * 0.06)

def calculate_case_46_tax(facts: Dict[str, Any]) -> float:
    """
    Case 46 確定性端到端微規則執行 (utils.pl: tax/3):
    由純粹底層事實推導申報身分、扣除額、免稅額與各項稅額。
    無任何 oracle 預設值。
    """
    taxpayer = facts["target_person"]
    spouse = facts.get("spouse")
    tax_year = facts["tax_year"]
    gross_income = facts["gross_income"]
    marriages = facts.get("marriages", [])
    joint_returns = facts.get("joint_returns", [])
    payments = facts.get("payments", [])
    services = facts.get("services", [])

    # 1. 嚴格由底層事實（婚姻關係與共同申報紀錄）推導申報身分，零 fallback
    filing_status = determine_filing_status(
        taxpayer=taxpayer,
        tax_year=tax_year,
        marriages=marriages,
        joint_returns=joint_returns,
        spouse=spouse
    )

    # 2. 標準扣除額與個人免稅額
    standard_deduction = compute_standard_deduction(filing_status, tax_year)
    exemption_count = 2 if filing_status == "married_joint" else 1
    exemptions = compute_personal_exemptions(gross_income, exemption_count, filing_status, tax_year)

    # 3. 課稅所得
    taxable_income = compute_taxable_income(gross_income, standard_deduction, exemptions)

    # 4. 所得稅：依推導出的 filing_status 匹配對應法定稅階
    if filing_status in ("married_joint", "surviving_spouse"):
        income_tax = calculate_income_tax_schedule_a(taxable_income)
    elif filing_status == "head_of_household":
        income_tax = calculate_income_tax_schedule_b(taxable_income)
    elif filing_status == "married_separate":
        income_tax = calculate_income_tax_schedule_d(taxable_income)
    else:  # single
        income_tax = calculate_income_tax_schedule_c(taxable_income)

    # 5. 農業雇主薪資稅 (SARA §3301 / §3306)
    employment_tax = calculate_agricultural_futa_tax(taxpayer, payments, services, tax_year)

    # 6. 稅額加總
    total_tax = income_tax + employment_tax
    return total_tax

if __name__ == "__main__":
    tax = calculate_case_46_tax(case_46_facts)
    print("=== Case 46 Micro-Rules Execution (SARA Benchmark Ground Truth) ===")
    print(f"Taxpayer: {case_46_facts['target_person']}")
    print(f"Spouse: {case_46_facts.get('spouse')}")
    print(f"Tax Year: {case_46_facts['tax_year']}")
    print(f"Gross Income: ${case_46_facts['gross_income']:,.2f}")

    derived_status = determine_filing_status(
        case_46_facts['target_person'],
        case_46_facts['tax_year'],
        case_46_facts.get('marriages', []),
        case_46_facts.get('joint_returns', []),
        case_46_facts.get('spouse')
    )
    std_ded = compute_standard_deduction(derived_status, case_46_facts['tax_year'])
    exempt = compute_personal_exemptions(case_46_facts['gross_income'], 2, derived_status, case_46_facts['tax_year'])
    taxable_inc = compute_taxable_income(case_46_facts['gross_income'], std_ded, exempt)
    inc_tax = calculate_income_tax_schedule_a(taxable_inc)
    emp_tax = calculate_agricultural_futa_tax(
        case_46_facts['target_person'],
        case_46_facts.get('payments', []),
        case_46_facts.get('services', []),
        case_46_facts['tax_year']
    )

    print(f"Derived Filing Status (Zero Fallback): {derived_status}")
    print(f"Standard Deduction (§63(c)(7)): ${std_ded:,.2f}")
    print(f"Personal Exemptions (§151(d)(5)): ${exempt:,.2f}")
    print(f"Taxable Income (§63): ${taxable_inc:,.2f}")
    print(f"Income Tax (§1(a)): ${inc_tax:,.2f}")
    print(f"Employment Tax (§3301 FUTA): ${emp_tax:,.2f}")
    print(f"Total Tax: ${tax:,.2f}")

    assert derived_status == "married_joint", f"Expected married_joint, got {derived_status}"
    assert tax == 17399.0, f"Expected 17399.0, got {tax}"
    print("SUCCESS: Case 46 tax matches SARA Prolog ground truth ($17,399.0) exactly!")
