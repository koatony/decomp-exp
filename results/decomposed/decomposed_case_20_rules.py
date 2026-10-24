import math
from enum import Enum
from pydantic import BaseModel, Field

# --- 1. Constants Pool (2017) ---

class FilingStatus(str, Enum):
    MARRIED_JOINTLY = "Married filing jointly / Surviving spouse"
    HEAD_OF_HOUSEHOLD = "Head of household"
    SINGLE = "Single"
    MARRIED_SEPARATELY = "Married filing separately"

# Standard Deductions (IRC §63)
STANDARD_DEDUCTIONS_2017 = {
    FilingStatus.MARRIED_JOINTLY: 6000.0,
    FilingStatus.HEAD_OF_HOUSEHOLD: 4400.0,
    FilingStatus.SINGLE: 3000.0,
    FilingStatus.MARRIED_SEPARATELY: 3000.0,
}

# Overall Limitation on Itemized Deductions (IRC §68 - Pease Limitation)
PEASE_LIMITATION_THRESHOLDS_2017 = {
    FilingStatus.MARRIED_JOINTLY: 300000.0,
    FilingStatus.HEAD_OF_HOUSEHOLD: 275000.0,
    FilingStatus.SINGLE: 250000.0,
    FilingStatus.MARRIED_SEPARATELY: 150000.0,
}
PEASE_LIMITATION_RATE_EXCESS = 0.03
PEASE_LIMITATION_RATE_ITEMIZED = 0.80

# Personal Exemptions & Phaseout (IRC §151 - PEP)
PERSONAL_EXEMPTION_AMOUNT_2017 = 2000.0
PEP_PHASEOUT_THRESHOLDS_2017 = PEASE_LIMITATION_THRESHOLDS_2017 # Same as Pease thresholds
PEP_PHASEOUT_REDUCTION_INCREMENT_GENERAL = 2500.0
PEP_PHASEOUT_REDUCTION_INCREMENT_MFS = 1250.0 # Married filing separately
PEP_PHASEOUT_RATE_PER_INCREMENT = 0.02 # 2 percentage points

# Tax Schedules (IRC §1) - (Bracket Max, Rate, Base Tax for previous bracket)
TAX_SCHEDULES_2017 = {
    FilingStatus.MARRIED_JOINTLY: [
        (36900.0, 0.15, 0.0),
        (89150.0, 0.28, 5535.0),
        (140000.0, 0.31, 20165.0),
        (250000.0, 0.36, 35928.50),
        (float('inf'), 0.396, 75528.50),
    ],
    FilingStatus.HEAD_OF_HOUSEHOLD: [
        (29600.0, 0.15, 0.0),
        (76400.0, 0.28, 4440.0),
        (127500.0, 0.31, 17544.0),
        (250000.0, 0.36, 33385.0),
        (float('inf'), 0.396, 77485.0),
    ],
    FilingStatus.SINGLE: [
        (22100.0, 0.15, 0.0),
        (53500.0, 0.28, 3315.0),
        (115000.0, 0.31, 12107.0),
        (250000.0, 0.36, 31172.0),
        (float('inf'), 0.396, 79772.0),
    ],
    FilingStatus.MARRIED_SEPARATELY: [
        (18450.0, 0.15, 0.0),
        (44575.0, 0.28, 2767.50),
        (70000.0, 0.31, 10082.50),
        (125000.0, 0.36, 17964.25),
        (float('inf'), 0.396, 37764.25),
    ],
}

# Employment / FUTA Tax (IRC §3301, §3306)
FUTA_WAGE_BASE_LIMIT_PER_EMPLOYEE_2017 = 7000.0
# Annual proxies for quarterly thresholds, as only annual wage data is provided.
FUTA_GENERAL_COMMERCIAL_ANNUAL_THRESHOLD_2017 = 1500.0 # Assumes $1500 in *any* quarter, so total annual must be at least this.
FUTA_DOMESTIC_SERVICE_ANNUAL_THRESHOLD_2017 = 1000.0 # Assumes $1000 in *any* quarter, so total annual must be at least this.
FUTA_AGRICULTURAL_LABOR_ANNUAL_THRESHOLD_2017 = 20000.0 # Assumes $20000 in *any* quarter, so total annual must be at least this.
FUTA_TAX_RATE_2017 = 0.06

# Rounding Rule
def round_half_up_to_nearest_integer(value: float) -> float:
    """Rounds a float half-up to the nearest integer (e.g., 2.5 rounds to 3)."""
    return math.floor(value + 0.5)

# --- 2. Decomposed Pydantic Models ---

class DecomposedTaxInputs(BaseModel):
    tax_year: int = Field(..., description="The tax year for the calculation (e.g., 2017).")
    filing_status: FilingStatus = Field(..., description="The taxpayer's filing status.")
    gross_income: float = Field(..., ge=0, description="The taxpayer's total gross income (assumed to be AGI for this problem).")
    itemized_deductions_claimed: float = Field(..., ge=0, description="Total itemized deductions claimed before any limitations.")
    num_dependents: int = Field(..., ge=0, description="Number of qualifying dependents.")
    
    # FUTA specific inputs (employer's perspective)
    employee_wages_paid: float = Field(..., ge=0, description="Total gross wages paid by the employer to all employees during the year.")
    employee_benefit_plan_exclusions: float = Field(..., ge=0, description="Total payments made under employee benefit plans excluded from FUTA wages.")
    num_employees: int = Field(..., ge=0, description="Total number of employees for the employer.")
    is_domestic_employer: bool = Field(False, description="True if the employer primarily employs domestic service workers.")
    is_agricultural_employer: bool = Field(False, description="True if the employer primarily employs agricultural labor.")

# --- 3. Intermediate Calculation Functions ---

def _calculate_standard_deduction(filing_status: FilingStatus) -> float:
    """Calculates the standard deduction based on filing status for 2017."""
    return STANDARD_DEDUCTIONS_2017.get(filing_status, 0.0)

def _calculate_pease_limitation(agi: float, itemized_deductions: float, filing_status: FilingStatus) -> float:
    """
    Calculates the reduction in itemized deductions due to the Pease Limitation (IRC §68) for 2017.
    Returns the *reduction amount*.
    """
    threshold = PEASE_LIMITATION_THRESHOLDS_2017.get(filing_status, float('inf'))
    
    if agi <= threshold:
        return 0.0
    
    excess_agi = agi - threshold
    
    reduction_by_excess = PEASE_LIMITATION_RATE_EXCESS * excess_agi
    reduction_by_itemized = PEASE_LIMITATION_RATE_ITEMIZED * itemized_deductions
    
    return min(reduction_by_excess, reduction_by_itemized)

def _calculate_allowable_itemized_deductions(agi: float, itemized_deductions_claimed: float, filing_status: FilingStatus) -> float:
    """
    Calculates the allowable itemized deductions after applying the Pease Limitation for 2017.
    """
    pease_reduction = _calculate_pease_limitation(agi, itemized_deductions_claimed, filing_status)
    return max(0.0, itemized_deductions_claimed - pease_reduction)

def _calculate_personal_exemption_amount(agi: float, num_exemptions: int, filing_status: FilingStatus) -> float:
    """
    Calculates the total personal exemption amount, including the PEP phaseout for 2017.
    """
    if num_exemptions <= 0:
        return 0.0

    base_exemption_total = num_exemptions * PERSONAL_EXEMPTION_AMOUNT_2017
    
    pep_threshold = PEP_PHASEOUT_THRESHOLDS_2017.get(filing_status, float('inf'))
    
    if agi <= pep_threshold:
        return base_exemption_total
    
    excess_agi = agi - pep_threshold
    
    if filing_status == FilingStatus.MARRIED_SEPARATELY:
        reduction_increment = PEP_PHASEOUT_REDUCTION_INCREMENT_MFS
    else:
        reduction_increment = PEP_PHASEOUT_REDUCTION_INCREMENT_GENERAL
        
    num_increments = math.ceil(excess_agi / reduction_increment)
    
    # Total percentage reduction (up to 100%)
    total_reduction_percentage = min(1.0, num_increments * PEP_PHASEOUT_RATE_PER_INCREMENT)
    
    return max(0.0, base_exemption_total * (1 - total_reduction_percentage))

def _calculate_tax_from_schedule(taxable_income: float, filing_status: FilingStatus) -> float:
    """
    Calculates income tax based on the provided tax schedule and taxable income for 2017.
    """
    if taxable_income <= 0:
        return 0.0

    schedule = TAX_SCHEDULES_2017.get(filing_status)
    if not schedule:
        raise ValueError(f"Tax schedule not found for filing status: {filing_status}")

    tax_due = 0.0
    previous_bracket_max = 0.0
    
    for bracket_max, rate, base_tax in schedule:
        if taxable_income <= bracket_max:
            tax_due = base_tax + (taxable_income - previous_bracket_max) * rate
            break
        previous_bracket_max = bracket_max
        
    return tax_due

def calculate_income_tax(inputs: DecomposedTaxInputs) -> float:
    """
    Calculates the personal income tax based on decomposed inputs for 2017.
    """
    # 1. Adjusted Gross Income (AGI) - assumed to be gross_income for this problem
    agi = inputs.gross_income

    # 2. Deductions: Choose greater of standard or allowable itemized
    allowable_itemized_deductions = _calculate_allowable_itemized_deductions(
        agi, inputs.itemized_deductions_claimed, inputs.filing_status
    )
    standard_deduction = _calculate_standard_deduction(inputs.filing_status)
    
    total_deductions = max(allowable_itemized_deductions, standard_deduction)

    # 3. Personal Exemptions: Taxpayer + dependents, subject to PEP phaseout
    num_eligible_exemptions = 1 + inputs.num_dependents # 1 for taxpayer, 1 for each qualifying dependent
    allowable_personal_exemptions = _calculate_personal_exemption_amount(
        agi, num_eligible_exemptions, inputs.filing_status
    )

    # 4. Taxable Income: AGI - Deductions - Exemptions (cannot be negative)
    taxable_income = max(0.0, agi - total_deductions - allowable_personal_exemptions)

    # 5. Tax Calculation from Schedule
    income_tax_raw = _calculate_tax_from_schedule(taxable_income, inputs.filing_status)
    
    return income_tax_raw

def calculate_employment_tax(inputs: DecomposedTaxInputs) -> float:
    """
    Calculates the FUTA employment tax based on decomposed inputs for 2017.
    Applies employer liability thresholds and wage base limits.
    """
    # Determine if employer is subject to FUTA based on annual wage thresholds.
    # Note: The statutory thresholds are quarterly. For this problem, we use
    # the annual total as a simplified proxy for meeting the quarterly condition.
    is_subject_to_futa = False
    if inputs.is_domestic_employer:
        if inputs.employee_wages_paid >= FUTA_DOMESTIC_SERVICE_ANNUAL_THRESHOLD_2017:
            is_subject_to_futa = True
    elif inputs.is_agricultural_employer:
        if inputs.employee_wages_paid >= FUTA_AGRICULTURAL_LABOR_ANNUAL_THRESHOLD_2017:
            is_subject_to_futa = True
    else: # General commercial employer
        if inputs.employee_wages_paid >= FUTA_GENERAL_COMMERCIAL_ANNUAL_THRESHOLD_2017:
            is_subject_to_futa = True

    if not is_subject_to_futa:
        return 0.0

    # Calculate taxable wages for FUTA
    # 1. Subtract benefit plan exclusions from gross wages
    net_wages_before_limit = max(0.0, inputs.employee_wages_paid - inputs.employee_benefit_plan_exclusions)

    # 2. Apply per-employee wage base limit.
    # The total maximum taxable wages for the employer is the sum of (min(wage_i, $7000)) for each employee.
    # Assuming `net_wages_before_limit` is the sum of all employees' wages after exclusions,
    # we cap this sum at `num_employees * $7000`.
    max_taxable_wages_for_employer = inputs.num_employees * FUTA_WAGE_BASE_LIMIT_PER_EMPLOYEE_2017
    
    futa_taxable_wages = min(net_wages_before_limit, max_taxable_wages_for_employer)
    
    # 3. Apply FUTA tax rate
    employment_tax_raw = futa_taxable_wages * FUTA_TAX_RATE_2017
    
    return employment_tax_raw

# --- 4. Top-Level Macro Rule ---

def calculate_total_tax(inputs: DecomposedTaxInputs) -> float:
    """
    Decomposed top-level macro rule:
    Calculates total tax by summing personal income tax and employer employment tax,
    applying the final rounding rule.
    """
    if inputs.tax_year != 2017:
        # In a real-world system, this would dynamically load rules for the given year.
        # For this problem, we are fixed to 2017 statutory provisions.
        raise ValueError(f"Tax year {inputs.tax_year} is not supported by this rule module. Only 2017 is implemented.")

    income_tax = calculate_income_tax(inputs)
    employment_tax = calculate_employment_tax(inputs)
    
    total_tax_raw = income_tax + employment_tax
    
    return round_half_up_to_nearest_integer(total_tax_raw)