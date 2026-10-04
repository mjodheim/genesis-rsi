"""Bounded target-blind inverse proposals from already paid quality sensors."""
from experiment.rsi_v48 import programs

MAX_OUTPUT_CALLS = 8192
MAX_PRIMITIVE_VISITS = 67108864


class Meter:
    def __init__(self):
        self.output_calls = 0
        self.primitive_visits = 0

    def outputs(self, genome, inputs):
        genome = programs.validate(genome)
        self.output_calls += 1
        if self.output_calls > MAX_OUTPUT_CALLS:
            raise ValueError("Externally fixed inference output cap exhausted")
        values = []
        for initial in inputs:
            value = initial
            for operation in genome["steps"]:
                self.primitive_visits += max(1, len(value)) if isinstance(value, (str, list, dict)) else 1
                if self.primitive_visits > MAX_PRIMITIVE_VISITS:
                    raise ValueError("Externally fixed inference primitive cap exhausted")
                domain = genome["domain"]
                if domain == "arithmetic":
                    if operation == 0:
                        value += 1
                    elif operation == 1:
                        value *= 2
                    elif operation == 2:
                        value += 3
                    else:
                        value = -value
                elif domain == "text":
                    if operation == 0:
                        value += "a"
                    elif operation == 1:
                        value = "x" + value
                    elif operation == 2:
                        value = value[::-1]
                    else:
                        value = value.replace("ab", "ba")
                elif domain == "sequence":
                    if operation == 0:
                        value = value[::-1]
                    elif operation == 1:
                        value = value[1:] + value[:1]
                    elif operation == 2:
                        value = [item + 1 for item in value]
                    else:
                        value = value + [0]
                elif operation == 0:
                    value = {key: item for key, item in value.items() if key != "noise"}
                elif operation == 1:
                    value = {("b" if key == "a" else key): item for key, item in value.items()}
                elif operation == 2:
                    value = {key: item + 1 for key, item in value.items()}
                else:
                    value = {**value, "field_" + str(len(value)): 0}
            if not programs.valid_value(genome["domain"], value):
                raise ValueError("Inference output exceeds pure grammar contract")
            values.append(value)
        return values


def propose(*, domain, inputs, revealed, rows, meter, similarity):
    """No target, evaluator object, target output or history task enters this ABI."""
    sensors = [(meter.outputs(genome, inputs), quality) for genome, quality in revealed]
    evaluated = {programs.descriptor(genome)["source_sha256"] for genome, _ in revealed}
    ranked = []
    for index, row in enumerate(rows):
        if row["source_sha256"] in evaluated:
            continue
        hypothesis = meter.outputs(row["candidate"], inputs)
        residual = sum(abs(sum(similarity(domain, actual, expected) for actual, expected in zip(outputs, hypothesis))
                           // len(inputs) - quality) for outputs, quality in sensors)
        ranked.append((residual, index, row))
    ranked.sort(key=lambda row: row[:2])
    return tuple({**row[2], "proposal_residual": row[0]} for row in ranked[:2])
