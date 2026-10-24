"""
SARA Case Loader & Fact Extractor:
Uses PurePrologDynamicTracer to execute SWI-Prolog directly on facts.
Dynamically retrieves active statutory clauses, proof paths, and grounded rules.
Zero Python heuristic if-else branching.
"""

from typing import Dict, Any
from rule_abstraction.parsers.pure_prolog_tracer import PurePrologDynamicTracer, SARA_V3_DIR

class SaraCaseLoader:
    def __init__(self, sara_v3_dir: str = SARA_V3_DIR):
        self.sara_v3_dir = sara_v3_dir
        self.tracer = PurePrologDynamicTracer(sara_v3_dir=sara_v3_dir)

    def load_case(self, case_id: str) -> Dict[str, Any]:
        """
        Executes SWI-Prolog on the case facts to dynamically extract:
        - Ground truth tax computed by SWI-Prolog
        - Activated statutory clauses (s1_c, s63_c, s3306_c_21, s1_a_1, etc.)
        - Activated Prolog source rules & documentation
        - Generic structured low_facts
        """
        return self.tracer.trace_case(case_id)
