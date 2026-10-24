import sys
sys.path.insert(0, "/home/wmlab/tax_agent")
from src.llm_client import LLMEngine

engine = LLMEngine()

prompt = """In 2017, Alice's gross income was $310,192. Alice has a father, Charlie, who retired in 2016 and had no income in 2017. Alice paid $5,322 into health insurance for Charlie.
Question: Under the Internal Revenue Code (specifically IRC §151 and §152(d) for the 2017 tax year), is Charlie a dependent (qualifying relative) of Alice, eligible for a personal exemption?
Please answer clearly Yes or No first, and explain:
1. Does a parent need to live in the taxpayer's principal home to be a qualifying relative under §152(d)(2)?
2. Does Charlie meet the gross income test under §152(d)(1)(B)?
3. Does Alice satisfy the support test?
"""

response = engine.generate(user_prompt=prompt)
print(response)