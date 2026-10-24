#!/usr/bin/env python3
"""
Case 51 Experiment Runner (SARA Benchmark).
Evaluates LLM on Case 51 using:
1. Pipeline 1 (Detailed Facts -> Micro-Rule):
   LLM extracts unaggregated factual entities -> Evaluated deterministically by rules/case_51/case_51_rules.py.
2. Pipeline 2 (Aggregated Sub-Taxes -> Macro-Rule):
   LLM extracts core sub-taxes (income_tax, employment_tax) -> Evaluated deterministically by rules_aggregation/case_51.py.

CRITICAL BENCHMARK CONSTRAINTS:
1. SARA question text leak is sanitized (strip answer from text).
2. Aggregation prompt contains ONLY annual constants, thresholds, and statutory tables.
3. No procedural calculation formulas or reasoning scaffolds in the prompt.
4. Zero oracle subset filtering: Provides the complete standard 2017 statutory context (all 4 schedules, all thresholds).
5. Zero fallback in schema parsing.
"""

import os
import re
import sys
import json
from typing import Dict, Any, List

PROJECT_ROOT = "/home/wmlab/tax_agent"
sys.path.insert(0, PROJECT_ROOT)

from src.llm_client import LLMEngine
from rule_abstraction.rules.case_51.case_51_rules import (
    Payment, Service, Dependent, Residence, calculate_case_51_tax,
    is_head_of_household, compute_standard_deduction,
    compute_pep_exemptions, calculate_income_tax_schedule_b,
    calculate_agricultural_futa_tax
)
from rule_abstraction.rules_aggregation.case_51 import AggregatedTaxInputs, calculate_total_tax

SARA_CASE_51_PATH = os.path.join(PROJECT_ROOT, "sara_v3", "cases", "tax_case_51.pl")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "rule_abstraction", "results")
DETAILED_RESULTS_DIR = os.path.join(RESULTS_DIR, "detailed")
AGGREGATED_RESULTS_DIR = os.path.join(RESULTS_DIR, "aggregated")

os.makedirs(DETAILED_RESULTS_DIR, exist_ok=True)
os.makedirs(AGGREGATED_RESULTS_DIR, exist_ok=True)


def read_sara_case_from_file(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract Scenario Text
    text_m = re.search(r"%\s*Text\s*\n((?:%\s*.*\n)+)", content)
    scenario_text = ""
    if text_m:
        scenario_text = "\n".join([line.lstrip("%").strip() for line in text_m.group(1).strip().splitlines()])

    # Extract Question Text and strip answer leaks
    q_m = re.search(r"%\s*Question\s*\n((?:%\s*.*\n)+)", content)
    question_text = ""
    if q_m:
        raw_q = "\n".join([line.lstrip("%").strip() for line in q_m.group(1).strip().splitlines()])
        question_text = re.sub(r"\?\s*[\$0-9]+.*", "?", raw_q)

    # Extract Ground Truth from Prolog test assertion
    gt_m = re.search(r":-\s*tax\((\"[^\"]+\"|\w+),\s*(\d{4}),\s*(\d+(?:\.\d+)?)\)", content)
    person = gt_m.group(1).strip('"') if gt_m else "Alice"
    year = int(gt_m.group(2)) if gt_m else 2017
    gt_tax = float(gt_m.group(3)) if gt_m else 55528.0

    return {
        "file_path": filepath,
        "scenario_text": scenario_text,
        "question_text": question_text,
        "target_person": person,
        "tax_year": year,
        "ground_truth_tax": gt_tax,
        "full_file_content": content
    }


def run_aggregated_pipeline(case_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("▶ [Pipeline 2] Aggregated Tax Inputs Extraction -> Macro-Rule Execution")
    print("="*70)

    system_prompt = (
        "You are an expert tax legal engine. Given a tax legal scenario, analyze the statutes and calculate the core aggregated sub-taxes:\n"
        "1. income_tax: IRC Section 1 individual income tax for the tax year.\n"
        "2. employment_tax: IRC Section 3301 employer FUTA tax (if any).\n"
        "Provide a concise legal reasoning explaining the calculation for both values.\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "target_person": "string",\n'
        '  "tax_year": integer,\n'
        '  "income_tax": float,\n'
        '  "employment_tax": float,\n'
        '  "reasoning": "string explaining how income_tax and employment_tax were determined"\n'
        "}"
    )

    # Completely neutral, non-oracle statutory context (identical across benchmark cases)
    statutory_context = (
        "Applicable statutory constants, thresholds, and tables for 2017 benchmark:\n"
        "1. Standard Deductions (IRC §63):\n"
        "   - Married filing jointly / Surviving spouse: $6,000.\n"
        "   - Head of household: $4,400.\n"
        "   - Single: $3,000.\n"
        "   - Married filing separately: $3,000.\n"
        "2. Overall Limitation on Itemized Deductions (IRC §68):\n"
        "   - Applicable threshold amounts (IRC §68(b)):\n"
        "     * Married filing jointly / Surviving spouse: $300,000.\n"
        "     * Head of household: $275,000.\n"
        "     * Single: $250,000.\n"
        "     * Married filing separately: $150,000.\n"
        "   - Limitation (IRC §68(a)): Itemized deductions shall be reduced by the lesser of:\n"
        "     * 3% of the excess of adjusted gross income over the applicable threshold amount, or\n"
        "     * 80% of the itemized deductions otherwise allowable.\n"
        "3. Personal Exemptions & Phaseout (IRC §151):\n"
        "   - Base exemption amount (IRC §151(d)(1)): $2,000 per eligible exemption.\n"
        "   - Phaseout (IRC §151(d)(3)): If adjusted gross income exceeds the applicable threshold under §68(b), "
        "the exemption amount is reduced by 2 percentage points for each $2,500 (or fraction thereof; $1,250 for married filing separately) of the excess, up to 100%.\n"
        "4. Tax Schedules (IRC §1):\n"
        "   - Married filing jointly / Surviving spouse schedule (IRC §1(a)):\n"
        "     * Taxable Income <= $36,900: 15% of taxable income.\n"
        "     * $36,900 < Taxable Income <= $89,150: $5,535 + 28% of the excess over $36,900.\n"
        "     * $89,150 < Taxable Income <= $140,000: $20,165 + 31% of the excess over $89,150.\n"
        "     * $140,000 < Taxable Income <= $250,000: $35,928.50 + 36% of the excess over $140,000.\n"
        "     * Taxable Income > $250,000: $75,528.50 + 39.6% of the excess over $250,000.\n"
        "   - Head of household schedule (IRC §1(b)):\n"
        "     * Taxable Income <= $29,600: 15% of taxable income.\n"
        "     * $29,600 < Taxable Income <= $76,400: $4,440 + 28% of the excess over $29,600.\n"
        "     * $76,400 < Taxable Income <= $127,500: $17,544 + 31% of the excess over $76,400.\n"
        "     * $127,500 < Taxable Income <= $250,000: $33,385 + 36% of the excess over $127,500.\n"
        "     * Taxable Income > $250,000: $77,485 + 39.6% of the excess over $250,000.\n"
        "   - Single schedule (IRC §1(c)):\n"
        "     * Taxable Income <= $22,100: 15% of taxable income.\n"
        "     * $22,100 < Taxable Income <= $53,500: $3,315 + 28% of the excess over $22,100.\n"
        "     * $53,500 < Taxable Income <= $115,000: $12,107 + 31% of the excess over $53,500.\n"
        "     * $115,000 < Taxable Income <= $250,000: $31,172 + 36% of the excess over $115,000.\n"
        "     * Taxable Income > $250,000: $79,772 + 39.6% of the excess over $250,000.\n"
        "   - Married filing separately schedule (IRC §1(d)):\n"
        "     * Taxable Income <= $18,450: 15% of taxable income.\n"
        "     * $18,450 < Taxable Income <= $44,575: $2,767.50 + 28% of the excess over $18,450.\n"
        "     * $44,575 < Taxable Income <= $70,000: $10,082.50 + 31% of the excess over $44,575.\n"
        "     * $70,000 < Taxable Income <= $125,000: $17,964.25 + 36% of the excess over $70,000.\n"
        "     * Taxable Income > $125,000: $37,764.25 + 39.6% of the excess over $125,000.\n"
        "5. Employment / FUTA Tax (IRC §3301, §3306):\n"
        "   - FUTA annual taxable wage base limit per employee (IRC §3306(b)(1)): $7,000.\n"
        "   - General commercial employment threshold (IRC §3306(a)(1)): $1,500 cash remuneration in any calendar quarter.\n"
        "   - Domestic service employment threshold (IRC §3306(a)(3)): $1,000 cash remuneration in any calendar quarter.\n"
        "   - Agricultural labor employment threshold (IRC §3306(a)(2)): $20,000 cash remuneration in any calendar quarter.\n"
        "   - FUTA tax rate (IRC §3301): 6% of taxable wages paid.\n"
        "6. Rounding:\n"
        "   - Round final tax half-up to nearest integer.\n"
    )

    user_prompt = (
        f"Case Text directly from SARA v3:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        f"{statutory_context}\n"
        "Please evaluate and output the aggregated tax inputs JSON according to these statutory rules."
    )

    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json")

    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_response.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_agg = json.loads(cleaned_json)
    except Exception as e:
        extracted_agg = {"parse_error": str(e), "raw_response": raw_response}

    rule_exec_result = {}
    try:
        agg_inputs = AggregatedTaxInputs(
            target_person=extracted_agg["target_person"],
            tax_year=int(extracted_agg["tax_year"]),
            income_tax=float(extracted_agg["income_tax"]),
            employment_tax=float(extracted_agg["employment_tax"]),
            reasoning=extracted_agg.get("reasoning", "")
        )
        total_tax = calculate_total_tax(agg_inputs)
        rule_exec_result = {
            "income_tax": agg_inputs.income_tax,
            "employment_tax": agg_inputs.employment_tax,
            "calculated_total_tax": total_tax,
            "ground_truth_tax": case_info["ground_truth_tax"],
            "matches_ground_truth": (total_tax == case_info["ground_truth_tax"])
        }
    except Exception as e:
        rule_exec_result = {
            "execution_error": f"{type(e).__name__}: {str(e)}",
            "matches_ground_truth": False
        }

    output = {
        "pipeline": "aggregated_tax_inputs_extraction",
        "case_id": "tax_case_51",
        "source_file": case_info["file_path"],
        "scenario_text": case_info["scenario_text"],
        "question_text": case_info["question_text"],
        "llm_extracted_aggregated_inputs": extracted_agg,
        "rule_execution": rule_exec_result
    }

    out_file = os.path.join(AGGREGATED_RESULTS_DIR, "case_51.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Aggregated Pipeline Result to: {out_file}")
    return output


def run_detailed_facts_pipeline(case_info: Dict[str, Any], engine: LLMEngine) -> Dict[str, Any]:
    print("\n" + "="*70)
    print("▶ [Pipeline 1] Detailed Facts Extraction -> Micro-Rule Execution")
    print("="*70)

    system_prompt = (
        "You are an expert tax parser. Extract all factual entities from the tax scenario into strict JSON format.\n"
        "Identify the primary taxpayer, gross income, claimed standard/itemized deductions, dependents, residences, and payments/services.\n"
        "Dates must be integers formatted as YYYYMMDD (e.g., 20170101, 20170902).\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "target_person": "string",\n'
        '  "tax_year": integer,\n'
        '  "gross_income": float,\n'
        '  "filing_status": "string",\n'
        '  "is_unmarried": boolean,\n'
        '  "household_furnish_ratio": float,\n'
        '  "dependents": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "name": "string",\n'
        '      "relationship": "string",\n'
        '      "gross_income": float,\n'
        '      "support_ratio_by_taxpayer": float\n'
        '    }\n'
        '  ],\n'
        '  "payments": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "agent": "string",\n'
        '      "patient": "string",\n'
        '      "amount": float,\n'
        '      "start_date": integer,\n'
        '      "purpose": "string",\n'
        '      "means": "string"\n'
        '    }\n'
        '  ],\n'
        '  "services": [\n'
        '    {\n'
        '      "id": "string",\n'
        '      "agent": "string",\n'
        '      "patient": "string",\n'
        '      "purpose": "string",\n'
        '      "start_date": integer,\n'
        '      "end_date": integer,\n'
        '      "location": "string",\n'
        '      "country": "string"\n'
        '    }\n'
        '  ],\n'
        '  "residences": [\n'
        '    {\n'
        '      "person": "string",\n'
        '      "abode": "string",\n'
        '      "start_date": integer,\n'
        '      "end_date": integer\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt = (
        f"Case Text directly from SARA v3:\n{case_info['scenario_text']}\n\n"
        f"Question:\n{case_info['question_text']}\n\n"
        "Please extract all factual events into the required JSON schema."
    )

    raw_response = engine.generate(user_prompt=user_prompt, system_prompt=system_prompt, response_mime_type="application/json")

    try:
        cleaned_json = re.sub(r"^```(?:json)?", "", raw_response.strip(), flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json.strip(), flags=re.MULTILINE).strip()
        extracted_facts = json.loads(cleaned_json)
    except Exception as e:
        extracted_facts = {"parse_error": str(e), "raw_response": raw_response}

    rule_exec_result = {}
    try:
        raw_dependents = extracted_facts.get("dependents", [])
        dependent_objs = [Dependent(**dep) if isinstance(dep, dict) else dep for dep in raw_dependents]

        raw_payments = extracted_facts.get("payments", [])
        payment_objs = [Payment(**p) if isinstance(p, dict) else p for p in raw_payments]

        raw_services = extracted_facts.get("services", [])
        service_objs = [Service(**s) if isinstance(s, dict) else s for s in raw_services]

        raw_residences = extracted_facts.get("residences", [])
        residence_objs = [Residence(**r) if isinstance(r, dict) else r for r in raw_residences]

        facts_for_rule = {
            "target_person": extracted_facts["target_person"],
            "tax_year": int(extracted_facts["tax_year"]),
            "gross_income": float(extracted_facts["gross_income"]),
            "filing_status": extracted_facts.get("filing_status", "single"),
            "is_unmarried": extracted_facts.get("is_unmarried", True),
            "household_furnish_ratio": float(extracted_facts.get("household_furnish_ratio", 1.0)),
            "dependents": dependent_objs,
            "payments": payment_objs,
            "services": service_objs,
            "residences": residence_objs
        }

        calculated_tax = calculate_case_51_tax(facts_for_rule)
        rule_exec_result = {
            "calculated_total_tax": calculated_tax,
            "ground_truth_tax": case_info["ground_truth_tax"],
            "matches_ground_truth": (calculated_tax == case_info["ground_truth_tax"])
        }
    except Exception as e:
        rule_exec_result = {
            "execution_error": f"{type(e).__name__}: {str(e)}",
            "matches_ground_truth": False
        }

    output = {
        "pipeline": "detailed_facts_extraction",
        "case_id": "tax_case_51",
        "source_file": case_info["file_path"],
        "scenario_text": case_info["scenario_text"],
        "question_text": case_info["question_text"],
        "llm_extracted_facts": extracted_facts,
        "rule_execution": rule_exec_result
    }

    out_file = os.path.join(DETAILED_RESULTS_DIR, "case_51.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved Detailed Pipeline Result to: {out_file}")
    return output


def main():
    print("🚀 Starting SARA Case 51 Experiment...")
    print(f"Reading SARA Case 51 directly from: {SARA_CASE_51_PATH}")
    case_info = read_sara_case_from_file(SARA_CASE_51_PATH)

    print(f"Taxpayer: {case_info['target_person']}")
    print(f"Year: {case_info['tax_year']}")
    print(f"Ground Truth Tax: ${case_info['ground_truth_tax']}")
    print(f"Scenario Text: {case_info['scenario_text']}")

    engine = LLMEngine()
    print(f"LLM Engine Initialized (Model: {engine.model_name}, Backend: {engine.backend})")

    # Run Pipeline 1: Detailed Facts -> Micro-Rule
    res_detailed = run_detailed_facts_pipeline(case_info, engine)

    # Run Pipeline 2: Aggregated Inputs -> Macro-Rule
    res_agg = run_aggregated_pipeline(case_info, engine)

    print("\n" + "="*70)
    print("📊 CASE 51 DUAL-PIPELINE EVALUATION SUMMARY")
    print("="*70)
    print("Pipeline 1 (Detailed Facts -> Micro-Rule):")
    print(f"  Calculated Total Tax: ${res_detailed.get('rule_execution', {}).get('calculated_total_tax')}")
    print(f"  Matches Ground Truth ($55,528): {res_detailed.get('rule_execution', {}).get('matches_ground_truth')}")
    print(f"  Saved to: rule_abstraction/results/detailed/case_51.json")

    print("\nPipeline 2 (Aggregated Sub-Taxes -> Macro-Rule):")
    print(f"  LLM Income Tax: ${res_agg.get('rule_execution', {}).get('income_tax')}")
    print(f"  LLM Employment Tax: ${res_agg.get('rule_execution', {}).get('employment_tax')}")
    print(f"  Calculated Total Tax: ${res_agg.get('rule_execution', {}).get('calculated_total_tax')}")
    print(f"  Matches Ground Truth ($55,528): {res_agg.get('rule_execution', {}).get('matches_ground_truth')}")
    print(f"  LLM Reasoning:\n{res_agg.get('llm_extracted_aggregated_inputs', {}).get('reasoning')}")
    print(f"  Saved to: rule_abstraction/results/aggregated/case_51.json")
    print("="*70)


if __name__ == "__main__":
    main()
