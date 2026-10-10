"""The first improver: ask the model for a better program, keep it when it scores higher.

Everything an improver is lies in this file: it is handed to itself as the program to improve.
"""
import re


def extract(reply):
    """The longest fenced block of the answer that parses as Python, or None. A program may itself
    contain fences, so the span from the first opening fence to the last closing one is tried too."""
    blocks = re.findall(r"```(?:python|py)?\n(.*?)```", reply, re.S)
    blocks += re.findall(r"```(?:python|py)?\n(.*)```", reply, re.S)
    for block in sorted(blocks, key=len, reverse=True):
        try:
            compile(block, "candidate.py", "exec")
            return block
        except SyntaxError:
            continue
    return None


def improve(task, lm, budget):
    best = task.initial
    best_score = task.utility(best)
    while budget.lm_calls_left > 0 and budget.evaluations_left > 0:
        reply = lm(
            "You are improving a program.\n\n" + task.description
            + f"\n\nCurrent best program (score {best_score:.4f}):\n```python\n{best}\n```\n\n"
            "Write a program that scores higher. Answer with the complete program in one ```python block.")
        candidate = extract(reply)
        if candidate is None:
            continue
        try:
            score = task.utility(candidate)
        except Exception:
            break
        if score > best_score:
            best, best_score = candidate, score
    return best
