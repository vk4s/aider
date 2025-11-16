watch_code_prompt = """
I've written your instructions in comments in the code and marked them with "ai"
You can see the "AI" comments shown below (marked with █).
Find them in the code files I've shared with you, and follow their instructions.

After completing those instructions, also be sure to remove all the "AI" comments from the code too.
"""

watch_ask_prompt = """/ask
Find the "AI" comments below (marked with █) in the code files I've shared with you.
They contain my questions that I need you to answer and other instructions for you.
"""

watch_architect_prompt = """/architect
Find the "AI" comments below (marked with █) in the code files I've shared with you.
Use them to produce an architecture-level plan and concrete edit guidance.
Do not dump entire files; reference paths and describe precise changes to make.
"""
