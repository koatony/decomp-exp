"""
Case 2: Alice & Bob's 2013 Married Filing Jointly Tax Rules and Facts.
Direct 1:1 translation from Prolog (tax_case_2.pl and statutory rules: utils.pl, section1.pl, section63.pl, section151.pl, section152.pl, section7703.pl).

Statutory Walkthrough:
1. Gross Income (utils.pl: gross_income/3):
   - Joint return in 2013: Alice ($65,400) + Bob ($56,400) = $121,800.
2. Standard Deduction (section63.pl: s63_c/3):
   - Joint return multiplier = 2 * default amount ($3,000) = $6,000.
3. Personal Exemptions (section151.pl: s151/5):
   - Alice ($2,000) + Bob ($2,000) + Charlie ($2,000 dependent under §152) = $6,000.
4. Taxable Income (section63.pl: s63/3):
   - $121,800 - ($6,000 standard deduction + $6,000 exemptions) = $109,800.
5. Income Tax (§1(a)(1) Married Filing Jointly):
   - Bracket (iii) [$89,150 to $140,000]:
     Tax = $20,165 + 31% * ($109,800 - $89,150) = $20,165 + $6,401.50 = $26,566.50 -> round = $26,567.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Income:
    id: str
    agent: str            # 賺取者 (Alice / Bob)
    amount: float         # 金額
    start_date: int       # 日期 (YYYYMMDD)

@dataclass
class Marriage:
    id: str
    spouses: List[str]    # 配偶名單 ["Alice", "Bob"]
    start_date: int

@dataclass
class Dependent:
    id: str
    name: str             # Charlie
    parents: List[str]    # ["Alice", "Bob"]
    birth_date: int

@dataclass
class JointReturn:
    id: str
    spouses: List[str]    # ["Alice", "Bob"]
    year: int

# ==============================================================================
# Case 2 原始事實 (Facts - 1:1 映射 Prolog tax_case_2.pl)
# ==============================================================================
case_2_facts: Dict[str, Any] = {
    "target_person": "Alice",
    "spouse": "Bob",
    "tax_year": 2013,
    "filing_status": "married_joint",
    "incomes": [
        Income(
            id="earned_340_345",
            agent="Alice",
            amount=65400.0,
            start_date=20130101
        ),
        Income(
            id="earned_362_367",
            agent="Bob",
            amount=56400.0,
            start_date=20130101
        )
    ],
    "marriage": Marriage(
        id="married_18_24",
        spouses=["Alice", "Bob"],
        start_date=19920203
    ),
    "dependents": [
        Dependent(
            id="child_65_69",
            name="Charlie",
            parents=["Alice", "Bob"],
            birth_date=20001009
        )
    ],
    "joint_return": JointReturn(
        id="jointly_283_289",
        spouses=["Alice", "Bob"],
        year=2013
    ),
    # 背景背景事實 (維持家庭費用 40%/60%、身故時間等，無直接稅額計算依賴)
    "alice_death_date": 20140709
}

# ==============================================================================
# Case 2 規則庫 (Rules - 1:1 映射 Prolog 呼叫到的法規條文)
# ==============================================================================

def compute_joint_gross_income(person: str, spouse: Optional[str], year: int, incomes: List[Income]) -> float:
    """
    對應 utils.pl: gross_income/3
    夫妻合併申報時，加總兩人該年度所有 income_ 與 payment_。
    """
    allowed_persons = {person}
    if spouse:
        allowed_persons.add(spouse)

    total = 0.0
    for inc in incomes:
        agent = inc.agent if isinstance(inc, Income) else inc.get("agent")
        amt = inc.amount if isinstance(inc, Income) else float(inc.get("amount", 0.0))
        s_date = inc.start_date if isinstance(inc, Income) else inc.get("start_date")

        if agent in allowed_persons:
            inc_year = int(str(s_date)[:4])
            if inc_year == year:
                total += amt
    return total

def get_standard_deduction_joint(year: int, filing_status: str) -> float:
    """
    對應 section63.pl: s63_c_2_A (夫妻合併申報標準扣除額)
    Multiplier = 2, 2013年預設金額 = $3,000 -> 2 * 3,000 = $6,000
    """
    if filing_status == "married_joint":
        return 6000.0
    return 3000.0

def compute_personal_exemptions(taxpayer_count: int, dependents_count: int, year: int) -> float:
    """
    對應 section151.pl: s151/5 (免稅額)
    2013年每人免稅額為 $2,000。
    夫妻2人 + 子女1人 = 3人 -> 3 * 2000 = $6,000
    """
    exemption_per_person = 2000.0
    total_persons = taxpayer_count + dependents_count
    return total_persons * exemption_per_person

def compute_taxable_income(gross_income: float, std_deduction: float, exemptions: float) -> float:
    """
    對應 section63.pl: s63_b/4
    應稅所得 = max(0, 總收入 - 標準扣除額 - 免稅額)
    """
    return max(0.0, gross_income - std_deduction - exemptions)

def compute_income_tax_s1_a(taxable_income: float) -> float:
    """
    對應 section1.pl: s1_a_tax/2 (夫妻合併申報稅階)
    (i)   <= 36,900: 15%
    (ii)  36,900 ~ 89,150: $5,535 + 28% * (Taxinc - 36,900)
    (iii) 89,150 ~ 140,000: $20,165 + 31% * (Taxinc - 89,150)
    (iv)  140,000 ~ 250,000: $35,928.50 + 36% * (Taxinc - 140,000)
    (v)   > 250,000: $75,528.50 + 39.6% * (Taxinc - 250,000)
    """
    if taxable_income <= 0:
        return 0.0
    elif taxable_income <= 36900:
        raw_tax = taxable_income * 0.15
    elif taxable_income <= 89150:
        raw_tax = 5535.0 + (taxable_income - 36900) * 0.28
    elif taxable_income <= 140000:
        raw_tax = 20165.0 + (taxable_income - 89150) * 0.31
    elif taxable_income <= 250000:
        raw_tax = 35928.50 + (taxable_income - 140000) * 0.36
    else:
        raw_tax = 75528.50 + (taxable_income - 250000) * 0.396

    # 對應 Prolog utils.pl: rounding/2 (F >= 0.5 -> +1 四捨五入，非 Python 的銀行家偶數捨入)
    import math
    return float(math.floor(raw_tax + 0.5))

def calculate_case_2_tax(facts: Dict[str, Any]) -> float:
    """
    對應 utils.pl: tax(Person, Year, Tax)
    Tax = 所得稅(§1(a)) + 雇主稅(§3301, 為0)
    """
    person = facts["target_person"]
    spouse = facts.get("spouse")
    year = facts["tax_year"]
    status = facts["filing_status"]

    # 1. 總收入 (Alice + Bob 加總)
    gross_income = compute_joint_gross_income(person, spouse, year, facts["incomes"])
    # 2. 標準扣除額 (MFJ: $6,000)
    std_deduction = get_standard_deduction_joint(year, status)
    # 3. 免稅額 (Alice + Bob + Charlie = 3 * $2,000 = $6,000)
    taxpayer_count = 2 if (status == "married_joint" and spouse) else 1
    dependents_count = len(facts.get("dependents", []))
    exemptions = compute_personal_exemptions(taxpayer_count, dependents_count, year)
    # 4. 應稅所得 ($121,800 - $6,000 - $6,000 = $109,800)
    taxable_income = compute_taxable_income(gross_income, std_deduction, exemptions)
    # 5. §1(a) 所得稅 ($20,165 + 31% * (109,800 - 89,150) = $26,567)
    income_tax = compute_income_tax_s1_a(taxable_income)
    # 6. §3301 薪資稅 (為0)
    employment_tax = 0.0

    return income_tax + employment_tax

if __name__ == "__main__":
    tax = calculate_case_2_tax(case_2_facts)
    print(f"=== Case 2 (Prolog -> Python 1:1) ===")
    print(f"Taxpayer: {case_2_facts['target_person']} & Spouse: {case_2_facts['spouse']}")
    print(f"Year: {case_2_facts['tax_year']}")
    gross = compute_joint_gross_income("Alice", "Bob", 2013, case_2_facts["incomes"])
    print(f"Joint Gross Income: ${gross}")
    print(f"Calculated Tax: ${tax}")
    assert tax == 26567.0, f"Expected 26567.0, got {tax}"
    print("SUCCESS: Case 2 tax calculation matches Prolog ground truth ($26,567) perfectly!")
