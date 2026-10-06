import asyncio
from core.llm import get_llm
from langchain.agents import create_agent
from core.middleware import SkillMiddleware
from langchain_core.messages import SystemMessage, HumanMessage

llm = get_llm()
agent = create_agent(model=llm, middleware=[SkillMiddleware()])
sys_msg = SystemMessage(content="""You are an expert regulatory compliance analyst. 
AGENT WORKFLOW:
1. Read the paragraph and check the Available Skills listed at the end of this prompt.
2. If the paragraph relates to one of the skills, you MUST call the read_skill tool with the skill name.
3. After reading the skill, proceed to generate your final analysis.

OUTPUT FORMAT — Once you have gathered the necessary context via tools, your FINAL response MUST be ONLY valid JSON matching this exact structure:
{
  "paragraph_text": "<exact paragraph text>"
}""")
user_msg = HumanMessage(content="""Analyse the following regulatory paragraph.

--- BEGIN PARAGRAPH ---
Banks are advised to maintain SLR of 18.00 per cent of their Net Demand and Time Liabilities (NDTL) with immediate effect.
--- END PARAGRAPH ---

Remember to call the read_skill tool FIRST if a skill applies (e.g., 'treasury-operations' based on SLR).""")

print('Invoking agent...')
result = agent.invoke({'messages': [sys_msg, user_msg]})
print('\\n\\n=== FINAL AGENT MESSAGES (Context including loaded skill) ===')
for m in result['messages']:
    print(f"\\n--- [Role: {m.type.upper()}] ---")
    if getattr(m, 'tool_calls', []):
        print(f"TOOL CALLS: {m.tool_calls}")
    print(m.content)
print('===========================================================\\n')

