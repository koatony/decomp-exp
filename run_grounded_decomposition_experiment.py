import os
import re
import sys
import json
from typing import Dict, Any

sys.path.insert(0, "/home/wmlab/tax_agent")
from src.llm_client import LLMEngine

OUTPUT_DIR = "/home/wmlab/tax_agent/rule_abstraction/results/grounded_decomposed"
os.makedirs(OUTPUT_DIR, exist_ok=True)
GENERATED_RULE_FILE = os.path.join(OUTPUT_DIR, "grounded_decomposed_case_20_rules.py")

COARSE_RULE_CODE = '''
from pydantic import BaseModel

class AggregatedTaxInputs(BaseModel):
    target_person: str
    tax_year: int
    income_tax: float
    employment_tax: float

def calculate_total_tax(inputs: AggregatedTaxInputs) -> float:
    return inputs.income_tax + inputs.employment_tax
'''

STATUTORY_POOL_2017 = '''Applicable Statutory Provisions, Thresholds, and Tables for 2017:

1. Standard Deductions (IRC §63):
   - Married filing jointly / Surviving spouse: $6,000.
   - Head of household: $4,400.
   - Single: $3,000.
   - Married filing separately: $3,000.

2. Overall Limitation on Itemized Deductions (IRC §68 - Pease Limitation):
   - Applicable threshold amount (IRC §68(b)):
     * Married filing jointly / Surviving spouse: $300,000.
     * Head of household: $275,000.
     * Single: $250,000.
     * Married filing separately: $150,000.
   - Limitation (IRC §68(a)): If adjusted gross income exceeds the applicable threshold amount,
     the amount of allowable itemized deductions is reduced by the lesser of:
     * 3% of the excess of adjusted gross income over the applicable threshold amount, or
     * 80% of the itemized deductions otherwise allowable.

3. Personal Exemptions & Phaseout (IRC §151 - PEP):
   - Base exemption amount (IRC §151(d)(1)): $2,000 per eligible exemption.
   - Eligibility (IRC §151(b), §152): 1 exemption for the taxpayer, and 1 exemption for each qualifying dependent (qualifying child or qualifying relative).
   - Phaseout (IRC §151(d)(3)): If adjusted gross income exceeds the applicable threshold under §68(b),
     the exemption amount is reduced by 2 percentage points for each $2,500 (or fraction thereof;
     $1,250 for married filing separately) of the excess, up to 100%.

4. Tax Schedules (IRC §1):
   - Married filing jointly / Surviving spouse schedule (IRC §1(a)):
     * Taxable Income <= $36,900: 15% of taxable income.
     * $36,900 < Taxable Income <= $89,150: $5,535 + 28% of the excess over $36,900.
     * $89,150 < Taxable Income <= $140,000: $20,165 + 31% of the excess over $89,150.
     * $140,000 < Taxable Income <= $250,000: $35,928.50 + 36% of the excess over $140,000.
     * Taxable Income > $250,000: $75,528.50 + 39.6% of the excess over $250,000.
   - Head of household schedule (IRC §1(b)):
     * Taxable Income <= $29,600: 15% of taxable income.
     * $29,600 < Taxable Income <= $76,400: $4,440 + 28% of the excess over $29,600.
     * $76,400 < Taxable Income <= $127,500: $17,544 + 31% of the excess over $76,400.
     * $127,500 < Taxable Income <= $250,000: $33,385 + 36% of the excess over $127,500.
     * Taxable Income > $250,000: $77,485 + 39.6% of the excess over $250,000.
   - Single schedule (IRC §1(c)):
     * Taxable Income <= $22,100: 15% of taxable income.
     * $22,100 < Taxable Income <= $53,500: $3,315 + 28% of the excess over $22,100.
     * $53,500 < Taxable Income <= $115,000: $12,107 + 31% of the excess over $53,500.
     * $115,000 < Taxable Income <= $250,000: $31,172 + 36% of the excess over $115,000.
     * Taxable Income > $250,000: $79,772 + 39.6% of the excess over $250,000.
   - Married filing separately schedule (IRC §1(d)):
     * Taxable Income <= $18,450: 15% of taxable income.
     * $18,450 < Taxable Income <= $44,575: $2,767.50 + 28% of the excess over $18,450.
     * $44,575 < Taxable Income <= $70,000: $10,082.50 + 31% of the excess over $44,575.
     * $70,000 < Taxable Income <= $125,000: $17,964.25 + 36% of the excess over $70,000.
     * Taxable Income > $125,000: $37,764.25 + 39.6% of the excess over $125,000.

5. Federal Unemployment Tax Act (FUTA, IRC §3301, §3306):
   - FUTA Tax Rate: 6.0% (0.06).
   - Wage Base Cap (IRC §3306(b)(1)): Tax applies only to the first $7,000 of remuneration paid by an employer to each employee during the calendar year.
   - Employer liability thresholds (IRC §3306(a)):
     * General employment: Employer paid wages of $1,500 or more in any calendar quarter.
     * Domestic service: Employer paid cash remuneration of $1,000 or more in any calendar quarter.
     * Agricultural labor: Employer paid cash remuneration of $20,000 or more in any calendar quarter.
   - Exclusions from wages (IRC §3306(b)(2), (b)(5)):
     * Payments made under a plan or system established by an employer on account of sickness, accident, or medical expenses.
     * Payments made to or on behalf of an employee under a retirement fund or trust.

6. Rounding Rule:
   - Round final taxes half-up to nearest integer (0.5 rounds up).
'''

SCENARIO_TEXT_CASE_20 = """In 2017, Alice's gross income was $310192. Since 2014, Alice maintains a house where she and her daughter live. Alice was married since Jan 14th, 2010 until her husband died on Nov 23rd, 2016. In 2017, Alice is allowed itemized deductions of $17890. Alice has paid $45252 to Bob for work done in the year 2017. In 2017, Alice has also paid $9832 into a retirement fund for Bob, and paid $5322 into health insurance for Charlie, who is Alice's father and has retired in 2016. Charlie had no income in 2017."""

def main():
    engine = LLMEngine()

    print("="*70)
    print("▶ Grounded Top-Down Rule Decomposition Experiment")
    print("="*70)

    prompt = f"""You are an expert tax domain modeler and Python software architect.
We want to decompose a coarse-grained tax rule into fine-grained, verifiable Python rules and Pydantic schemas.

### 1. Existing Coarse Rule
```python
{COARSE_RULE_CODE}
```

### 2. Statutory Pool (2017)
{STATUTORY_POOL_2017}

### 3. Concrete Benchmark Scenario Example
```
{SCENARIO_TEXT_CASE_20}
```

### 4. CRITICAL DECOMPOSITION INSTRUCTION: Extractability Constraint
All variables defined in your intermediate Pydantic schema MUST BE DIRECTLY EXTRACTABLE ATOMIC FACTS from the scenario text.
- If a high-level concept is explicitly stated in the text (e.g. "gross income $310192"), it can be a variable.
- But if a high-level legal concept is NOT explicitly named in the text (for example, filing status like "surviving spouse", or aggregate count of dependents ), YOU MUST NOT create an abstract variable for it!
- Instead, you MUST decompose that concept into the elemental, factual primitives that appear in the scenario (e.g., marriage date, spouse death date, maintaining a household, child living with taxpayer, dependents' relationship and gross income, payments made, purpose/plan type of payments).
- Define a top-level input schema `GroundedTaxInputs` containing only these extractable atomic facts, and a function `calculate_total_tax(inputs: GroundedTaxInputs) -> float`.

Return ONLY the complete, executable Python code inside a single ```python ... ``` markdown block.
"""

    print("⏳ Calling Gemini 2.5 Flash for Grounded Decomposition...")
    resp = engine.generate(user_prompt=prompt, temperature=0.0)

    code_match = re.search(r"```python(.*?)```", resp, re.DOTALL)
    extracted_code = code_match.group(1).strip() if code_match else resp.strip()

    with open(GENERATED_RULE_FILE, "w", encoding="utf-8") as f:
        f.write(extracted_code)
    print(f"✅ Saved generated rules to: {GENERATED_RULE_FILE}")

if __name__ == "__main__":
    main()
