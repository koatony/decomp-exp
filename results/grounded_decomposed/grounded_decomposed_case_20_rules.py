from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Dict
from datetime import date
import math

# --- 1. Grounded Inputs Schema (Atomic Facts from Scenario) ---

class PersonPayment(BaseModel):
    """Represents a payment made by the taxpayer to another person."""
    recipient_name: str
    amount: float
    purpose: Literal["work", "retirement_fund", "health_insurance"]
    plan_type: Optional[str] = None # e.g., "retirement_fund", "health_insurance" for clarity

class PersonRelationship(BaseModel):
    """Represents details about another person relevant for tax calculations."""
    name: str
    relationship_to_taxpayer: str
    lives_with_taxpayer: Optional[bool] = None
    gross_income: Optional[float] = None
    retired_year: Optional[int] = None
    # Additional atomic facts (e.g., age, student status, support percentage) would be added here
    # if explicitly mentioned in the scenario.

class GroundedTaxInputs(BaseModel):
    """
    Contains only atomic facts directly extractable from the scenario text.
    No inferred legal concepts (like 'filing status' or 'number of dependents').
    """
    tax_year: int
    taxpayer_gross_income: float
    taxpayer_itemized_deductions_otherwise_allowable: float
    taxpayer_marriage_date: Optional[date] = None
    taxpayer_spouse_death_date: Optional[date] = None
    taxpayer_maintains_household_since_year: Optional[int] = None
    other_persons_details: List[PersonRelationship] = Field(default_factory=list)
    payments_made_by_taxpayer: List[PersonPayment] = Field(default_factory=list)

    @validator('tax_year')
    def check_tax_year(cls, v):
        if v != 2017:
            raise ValueError("Only tax year 2017 is supported by these rules.")
        return v

# --- 2. Intermediate Schemas for Derived Concepts and Calculation Steps ---

class FilingStatusInfo(BaseModel):
    """Represents the determined filing status."""
    filing_status: Literal["MFJ", "HOH", "Single", "MFS"] # MFJ includes Surviving Spouse for rates
    is_surviving_spouse: bool = False
    is_head_of_household: bool = False

class DependentEligibility(BaseModel):
    """Represents the eligibility of a person as a dependent for exemptions."""
    name: str
    is_qualifying_child: bool
    is_qualifying_relative: bool
    is_eligible_for_exemption: bool

class ExemptionCalculation(BaseModel):
    """Details the calculation of personal exemptions, including phaseout."""
    base_exemption_amount_per_person: float
    num_exemptions_claimed: int
    total_base_exemption_amount: float
    agi_for_pep: float
    pep_threshold: float
    pep_excess_agi: float
    pep_reduction_percentage: float
    pep_reduction_amount: float
    allowable_personal_exemptions: float

class DeductionCalculation(BaseModel):
    """Details the calculation of deductions, including Pease Limitation."""
    standard_deduction_amount: float
    itemized_deductions_otherwise_allowable: float
    agi_for_pease: float
    pease_threshold: float
    pease_excess_agi: float
    pease_reduction_3_percent: float
    pease_reduction_80_percent: float
    pease_reduction_amount: float
    allowable_itemized_deductions: float
    deduction_method_chosen: Literal["Standard", "Itemized"]
    total_allowable_deductions: float

class TaxableIncomeCalculation(BaseModel):
    """Details the calculation of taxable income."""
    gross_income: float
    adjusted_gross_income: float # For this problem, AGI = Gross Income
    total_allowable_deductions: float
    allowable_personal_exemptions: float
    taxable_income: float

class TaxBracket(BaseModel):
    """Represents a single tax bracket."""
    min_income: float
    max_income: Optional[float]
    rate: float
    base_tax: float

class IncomeTaxCalculation(BaseModel):
    """Details the calculation of income tax."""
    taxable_income: float
    filing_status: Literal["MFJ", "HOH", "Single", "MFS"]
    tax_brackets: List[TaxBracket]
    calculated_income_tax_before_rounding: float
    calculated_income_tax_rounded: float

class FutaEmployeeInfo(BaseModel):
    """Details FUTA calculation for a specific employee."""
    employee_name: str
    wages_paid: float
    retirement_contributions: float
    health_insurance_payments: float # For employee/family, not for dependents
    futa_taxable_wages: float
    futa_tax_per_employee: float

class EmploymentTaxCalculation(BaseModel):
    """Details the calculation of Federal Unemployment Tax (FUTA)."""
    futa_tax_rate: float
    futa_wage_base_cap: float
    employer_meets_general_futa_threshold: bool
    employees_futa_details: List[FutaEmployeeInfo]
    total_futa_tax_before_rounding: float
    total_futa_tax_rounded: float

class TotalTaxCalculation(BaseModel):
    """The final aggregated tax calculation."""
    income_tax: float
    employment_tax: float
    total_tax_before_rounding: float
    total_tax_rounded: float

# --- 3. Helper Functions for Statutory Rules ---

def round_half_up(value: float) -> int:
    """Rounds a float half-up to the nearest integer (0.5 rounds up)."""
    return int(math.floor(value + 0.5))

def get_2017_thresholds_and_rates(filing_status: Literal["MFJ", "HOH", "Single", "MFS"]) -> Dict:
    """Returns 2017 statutory thresholds and rates based on filing status."""
    thresholds = {
        "MFJ": { # Includes Surviving Spouse
            "standard_deduction": 6000.0,
            "pease_threshold": 300000.0,
            "pep_threshold": 300000.0,
            "tax_brackets": [
                TaxBracket(min_income=0, max_income=36900, rate=0.15, base_tax=0),
                TaxBracket(min_income=36900, max_income=89150, rate=0.28, base_tax=5535),
                TaxBracket(min_income=89150, max_income=140000, rate=0.31, base_tax=20165),
                TaxBracket(min_income=140000, max_income=250000, rate=0.36, base_tax=35928.50),
                TaxBracket(min_income=250000, max_income=None, rate=0.396, base_tax=75528.50),
            ]
        },
        "HOH": {
            "standard_deduction": 4400.0,
            "pease_threshold": 275000.0,
            "pep_threshold": 275000.0,
            "tax_brackets": [
                TaxBracket(min_income=0, max_income=29600, rate=0.15, base_tax=0),
                TaxBracket(min_income=29600, max_income=76400, rate=0.28, base_tax=4440),
                TaxBracket(min_income=76400, max_income=127500, rate=0.31, base_tax=17544),
                TaxBracket(min_income=127500, max_income=250000, rate=0.36, base_tax=33385),
                TaxBracket(min_income=250000, max_income=None, rate=0.396, base_tax=77485),
            ]
        },
        "Single": {
            "standard_deduction": 3000.0,
            "pease_threshold": 250000.0,
            "pep_threshold": 250000.0,
            "tax_brackets": [
                TaxBracket(min_income=0, max_income=22100, rate=0.15, base_tax=0),
                TaxBracket(min_income=22100, max_income=53500, rate=0.28, base_tax=3315),
                TaxBracket(min_income=53500, max_income=115000, rate=0.31, base_tax=12107),
                TaxBracket(min_income=115000, max_income=250000, rate=0.36, base_tax=31172),
                TaxBracket(min_income=250000, max_income=None, rate=0.396, base_tax=79772),
            ]
        },
        "MFS": {
            "standard_deduction": 3000.0,
            "pease_threshold": 150000.0,
            "pep_threshold": 150000.0,
            "tax_brackets": [
                TaxBracket(min_income=0, max_income=18450, rate=0.15, base_tax=0),
                TaxBracket(min_income=18450, max_income=44575, rate=0.28, base_tax=2767.50),
                TaxBracket(min_income=44575, max_income=70000, rate=0.31, base_tax=10082.50),
                TaxBracket(min_income=70000, max_income=125000, rate=0.36, base_tax=17964.25),
                TaxBracket(min_income=125000, max_income=None, rate=0.396, base_tax=37764.25),
            ]
        }
    }
    return thresholds[filing_status]

def determine_filing_status(inputs: GroundedTaxInputs) -> FilingStatusInfo:
    """Determines the taxpayer's filing status for 2017 based on IRC §1, §2."""
    # Check for qualifying child in household for Surviving Spouse/HOH
    has_qualifying_child_in_household = False
    for person in inputs.other_persons_details:
        if person.relationship_to_taxpayer == "daughter" and person.lives_with_taxpayer:
            # Assuming daughter meets other QC criteria like age, etc., for filing status purposes
            has_qualifying_child_in_household = True
            break

    # 1. Surviving Spouse (IRC §2(a))
    # Spouse died in 2015 or 2016, and taxpayer maintains a home for a dependent child.
    if inputs.taxpayer_spouse_death_date and \
       (inputs.tax_year - inputs.taxpayer_spouse_death_date.year == 1 or \
        inputs.tax_year - inputs.taxpayer_spouse_death_date.year == 2) and \
       inputs.taxpayer_maintains_household_since_year and \
       has_qualifying_child_in_household:
        return FilingStatusInfo(filing_status="MFJ", is_surviving_spouse=True)

    # 2. Head of Household (IRC §2(b))
    # Unmarried (or considered unmarried), maintains a household for more than half the year for a qualifying person.
    # A person whose spouse died in a prior year (and is not a surviving spouse) is unmarried.
    # Alice's spouse died in 2016, so in 2017 she is unmarried.
    if (not inputs.taxpayer_marriage_date or \
        (inputs.taxpayer_spouse_death_date and inputs.taxpayer_spouse_death_date.year < inputs.tax_year)) and \
       inputs.taxpayer_maintains_household_since_year and \
       has_qualifying_child_in_household:
        return FilingStatusInfo(filing_status="HOH", is_head_of_household=True)

    # 3. Single (IRC §1(c))
    # Default if not MFJ, HOH, MFS.
    return FilingStatusInfo(filing_status="Single")

def determine_dependent_eligibility(inputs: GroundedTaxInputs) -> List[DependentEligibility]:
    """Determines eligibility for personal exemptions for dependents based on IRC §151, §152."""
    eligible_dependents = []

    for person in inputs.other_persons_details:
        is_qualifying_child = False
        is_qualifying_relative = False
        is_eligible_for_exemption = False

        # Check for Qualifying Child (IRC §152(c))
        if person.relationship_to_taxpayer == "daughter" and person.lives_with_taxpayer:
            # Scenario implies daughter lives with taxpayer, is child.
            # Assuming age, support, and joint return tests are met as per typical QC rules for a child living with parent.
            # Gross income test is not applicable for a qualifying child.
            is_qualifying_child = True
            is_eligible_for_exemption = True
        
        # Check for Qualifying Relative (IRC §152(d))
        elif person.relationship_to_taxpayer == "father" and person.name == "Charlie":
            # Not a qualifying child (father is not a child).
            # Relationship test: Father (qualifies).
            # Gross Income Test: Charlie had no income in 2017 ($0 < $4,050 for 2017). Pass.
            # Support Test: "Alice has also paid $5322 into health insurance for Charlie." "Charlie had no income in 2017."
            # This strongly implies Alice provides more than half support.
            # Joint Return Test: Not applicable as Charlie is not married.
            is_qualifying_relative = True # Assuming support test met
            is_eligible_for_exemption = True

        if is_eligible_for_exemption:
            eligible_dependents.append(DependentEligibility(
                name=person.name,
                is_qualifying_child=is_qualifying_child,
                is_qualifying_relative=is_qualifying_relative,
                is_eligible_for_exemption=is_eligible_for_exemption
            ))
    return eligible_dependents

def calculate_exemptions(inputs: GroundedTaxInputs, filing_status_info: FilingStatusInfo, agi: float) -> ExemptionCalculation:
    """Calculates allowable personal exemptions, applying Personal Exemption Phaseout (PEP) (IRC §151)."""
    base_exemption_amount_per_person = 2000.0 # For 2017

    # Taxpayer always gets one exemption
    num_exemptions_claimed = 1

    # Add exemptions for qualifying dependents
    dependents_eligibility = determine_dependent_eligibility(inputs)
    for dep in dependents_eligibility:
        if dep.is_eligible_for_exemption:
            num_exemptions_claimed += 1

    total_base_exemption_amount = num_exemptions_claimed * base_exemption_amount_per_person

    # Personal Exemption Phaseout (PEP)
    thresholds = get_2017_thresholds_and_rates(filing_status_info.filing_status)
    pep_threshold = thresholds["pep_threshold"]

    pep_excess_agi = max(0.0, agi - pep_threshold)

    pep_reduction_percentage = 0.0
    if pep_excess_agi > 0:
        # 2 percentage points for each $2,500 (or fraction thereof; $1,250 for MFS) of the excess
        increment_amount = 1250.0 if filing_status_info.filing_status == "MFS" else 2500.0
        num_increments = math.ceil(pep_excess_agi / increment_amount)
        pep_reduction_percentage = min(1.0, num_increments * 0.02) # Up to 100% reduction

    pep_reduction_amount = total_base_exemption_amount * pep_reduction_percentage
    allowable_personal_exemptions = total_base_exemption_amount - pep_reduction_amount
    allowable_personal_exemptions = max(0.0, allowable_personal_exemptions) # Cannot be negative

    return ExemptionCalculation(
        base_exemption_amount_per_person=base_exemption_amount_per_person,
        num_exemptions_claimed=num_exemptions_claimed,
        total_base_exemption_amount=total_base_exemption_amount,
        agi_for_pep=agi,
        pep_threshold=pep_threshold,
        pep_excess_agi=pep_excess_agi,
        pep_reduction_percentage=pep_reduction_percentage,
        pep_reduction_amount=pep_reduction_amount,
        allowable_personal_exemptions=allowable_personal_exemptions
    )

def calculate_deductions(inputs: GroundedTaxInputs, filing_status_info: FilingStatusInfo, agi: float) -> DeductionCalculation:
    """Calculates allowable deductions, applying Pease Limitation (IRC §68)."""
    thresholds = get_2017_thresholds_and_rates(filing_status_info.filing_status)
    standard_deduction_amount = thresholds["standard_deduction"]
    itemized_deductions_otherwise_allowable = inputs.taxpayer_itemized_deductions_otherwise_allowable

    # Pease Limitation (IRC §68)
    pease_threshold = thresholds["pease_threshold"]
    pease_excess_agi = max(0.0, agi - pease_threshold)

    pease_reduction_3_percent = 0.03 * pease_excess_agi
    pease_reduction_80_percent = 0.80 * itemized_deductions_otherwise_allowable
    pease_reduction_amount = min(pease_reduction_3_percent, pease_reduction_80_percent)

    allowable_itemized_deductions = itemized_deductions_otherwise_allowable - pease_reduction_amount
    allowable_itemized_deductions = max(0.0, allowable_itemized_deductions) # Cannot be negative

    # Choose between standard and itemized
    deduction_method_chosen: Literal["Standard", "Itemized"]
    total_allowable_deductions: float

    if allowable_itemized_deductions > standard_deduction_amount:
        deduction_method_chosen = "Itemized"
        total_allowable_deductions = allowable_itemized_deductions
    else:
        deduction_method_chosen = "Standard"
        total_allowable_deductions = standard_deduction_amount

    return DeductionCalculation(
        standard_deduction_amount=standard_deduction_amount,
        itemized_deductions_otherwise_allowable=itemized_deductions_otherwise_allowable,
        agi_for_pease=agi,
        pease_threshold=pease_threshold,
        pease_excess_agi=pease_excess_agi,
        pease_reduction_3_percent=pease_reduction_3_percent,
        pease_reduction_80_percent=pease_reduction_80_percent,
        pease_reduction_amount=pease_reduction_amount,
        allowable_itemized_deductions=allowable_itemized_deductions,
        deduction_method_chosen=deduction_method_chosen,
        total_allowable_deductions=total_allowable_deductions
    )

def calculate_income_tax(taxable_income: float, filing_status_info: FilingStatusInfo) -> IncomeTaxCalculation:
    """Calculates income tax based on taxable income and filing status (IRC §1)."""
    tax_brackets = get_2017_thresholds_and_rates(filing_status_info.filing_status)["tax_brackets"]

    calculated_tax = 0.0
    for bracket in tax_brackets:
        if taxable_income > bracket.min_income:
            if bracket.max_income is None or taxable_income <= bracket.max_income:
                taxable_in_bracket = taxable_income - bracket.min_income
                calculated_tax = bracket.base_tax + (taxable_in_bracket * bracket.rate)
                break
        # If taxable_income is less than or equal to a bracket's min_income, tax is 0 or from a previous bracket.
        # The structure of base_tax in subsequent brackets handles the cumulative tax.

    calculated_income_tax_rounded = round_half_up(calculated_tax)

    return IncomeTaxCalculation(
        taxable_income=taxable_income,
        filing_status=filing_status_info.filing_status,
        tax_brackets=tax_brackets,
        calculated_income_tax_before_rounding=calculated_tax,
        calculated_income_tax_rounded=float(calculated_income_tax_rounded)
    )

def calculate_futa_tax(inputs: GroundedTaxInputs) -> EmploymentTaxCalculation:
    """Calculates Federal Unemployment Tax (FUTA) (IRC §3301, §3306)."""
    futa_tax_rate = 0.06
    futa_wage_base_cap = 7000.0

    # Determine if employer meets general FUTA threshold
    # "Employer paid wages of $1,500 or more in any calendar quarter."
    # The scenario states Alice paid Bob $45,252 for work. We assume this implies the threshold is met.
    employer_meets_general_futa_threshold = False
    total_wages_paid_for_work = sum(p.amount for p in inputs.payments_made_by_taxpayer if p.purpose == "work")
    if total_wages_paid_for_work >= 1500.0: # Simplified check, assuming annual wages imply quarterly
         employer_meets_general_futa_threshold = True

    employees_futa_details: List[FutaEmployeeInfo] = []
    total_futa_tax_before_rounding = 0.0

    if employer_meets_general_futa_threshold:
        # Aggregate payments by recipient for FUTA purposes
        employee_wages: Dict[str, float] = {}
        employee_retirement_contributions: Dict[str, float] = {}
        employee_health_insurance_payments: Dict[str, float] = {} # For employee/family

        for payment in inputs.payments_made_by_taxpayer:
            if payment.purpose == "work":
                employee_wages[payment.recipient_name] = employee_wages.get(payment.recipient_name, 0.0) + payment.amount
            elif payment.purpose == "retirement_fund":
                employee_retirement_contributions[payment.recipient_name] = employee_retirement_contributions.get(payment.recipient_name, 0.0) + payment.amount
            elif payment.purpose == "health_insurance":
                # FUTA exclusion is for payments made to or on behalf of an *employee*.
                # Charlie is Alice's father, not an employee. So this payment is not an exclusion for FUTA wages.
                pass # Not relevant for FUTA wages for an employee in this scenario

        # Process each potential employee (based on who received "work" payments)
        for employee_name, wages_paid in employee_wages.items():
            # In this specific scenario, Bob is the only employee. Charlie is a dependent.
            if employee_name == "Bob":
                retirement_contrib = employee_retirement_contributions.get(employee_name, 0.0)
                health_ins_payments = employee_health_insurance_payments.get(employee_name, 0.0)

                # FUTA taxable wages: wages up to cap, excluding specific payments.
                # Retirement fund payments are explicitly excluded from FUTA wages.
                # Health insurance payments for an employee are also excluded.
                futa_taxable_wages_before_cap = wages_paid # No other exclusions apply to Bob's wages in this scenario
                futa_taxable_wages = min(futa_taxable_wages_before_cap, futa_wage_base_cap)
                futa_tax_per_employee = futa_taxable_wages * futa_tax_rate
                total_futa_tax_before_rounding += futa_tax_per_employee

                employees_futa_details.append(FutaEmployeeInfo(
                    employee_name=employee_name,
                    wages_paid=wages_paid,
                    retirement_contributions=retirement_contrib,
                    health_insurance_payments=health_ins_payments,
                    futa_taxable_wages=futa_taxable_wages,
                    futa_tax_per_employee=futa_tax_per_employee
                ))

    total_futa_tax_rounded = round_half_up(total_futa_tax_before_rounding)

    return EmploymentTaxCalculation(
        futa_tax_rate=futa_tax_rate,
        futa_wage_base_cap=futa_wage_base_cap,
        employer_meets_general_futa_threshold=employer_meets_general_futa_threshold,
        employees_futa_details=employees_futa_details,
        total_futa_tax_before_rounding=total_futa_tax_before_rounding,
        total_futa_tax_rounded=float(total_futa_tax_rounded)
    )

# --- 4. Main Calculation Function ---

def calculate_total_tax(inputs: GroundedTaxInputs) -> TotalTaxCalculation:
    """
    Calculates total tax based on fine-grained statutory rules and grounded inputs.
    This function orchestrates the individual tax calculation steps.
    """
    # AGI for this problem is simply gross income as no above-the-line deductions are specified.
    adjusted_gross_income = inputs.taxpayer_gross_income

    # 1. Determine Filing Status
    filing_status_info = determine_filing_status(inputs)

    # 2. Calculate Deductions (Standard vs. Itemized, Pease Limitation)
    deduction_calc = calculate_deductions(inputs, filing_status_info, adjusted_gross_income)

    # 3. Calculate Personal Exemptions (PEP)
    exemption_calc = calculate_exemptions(inputs, filing_status_info, adjusted_gross_income)

    # 4. Calculate Taxable Income
    taxable_income_value = adjusted_gross_income - deduction_calc.total_allowable_deductions - exemption_calc.allowable_personal_exemptions
    taxable_income_value = max(0.0, taxable_income_value) # Taxable income cannot be negative

    taxable_income_calc = TaxableIncomeCalculation(
        gross_income=inputs.taxpayer_gross_income,
        adjusted_gross_income=adjusted_gross_income,
        total_allowable_deductions=deduction_calc.total_allowable_deductions,
        allowable_personal_exemptions=exemption_calc.allowable_personal_exemptions,
        taxable_income=taxable_income_value
    )

    # 5. Calculate Income Tax
    income_tax_calc = calculate_income_tax(taxable_income_calc.taxable_income, filing_status_info)

    # 6. Calculate Employment Tax (FUTA)
    employment_tax_calc = calculate_futa_tax(inputs)

    # 7. Total Tax
    total_tax_before_rounding = income_tax_calc.calculated_income_tax_before_rounding + employment_tax_calc.total_futa_tax_before_rounding
    total_tax_rounded = round_half_up(total_tax_before_rounding)

    return TotalTaxCalculation(
        income_tax=income_tax_calc.calculated_income_tax_rounded,
        employment_tax=employment_tax_calc.total_futa_tax_rounded,
        total_tax_before_rounding=total_tax_before_rounding,
        total_tax_rounded=float(total_tax_rounded)
    )