"""Conditional symbolic archive model; no measured native efficiency claim."""
import itertools

from experiment.rsi_v50.native import word


def products(library):
    values = tuple(sorted({word(value) for value in library}))
    if len(values) != 4 or not values[0] or len({len(value) for value in values}) != 1:
        raise ValueError("The continuation premise requires four distinct equal-length tools")
    return tuple(left + right for left, right in itertools.product(values, repeat=2))


def search(library, feedback):
    """Feedback is an external whole-program equality decision; no target input."""
    paid = []
    for proposed in products(library):
        accepted = feedback(proposed)
        if type(accepted) is not bool:
            raise ValueError("Nonboolean mathematical feedback")
        paid.append({"word": list(proposed), "accepted": accepted})
        if accepted:
            if feedback(proposed) is not True:
                raise ValueError("Mathematical confirmation disagrees")
            paid.append({"word": list(proposed), "accepted": True, "confirmation": True})
            return {"solved": True, "word": proposed, "calls": paid}
    return {"solved": False, "word": None, "calls": paid}


def exact_equality_oracle(target):
    # In this model, equality of words is equivalent to equality of native output
    # at any nonempty base text outside the four output languages, by the proof.
    target = word(target)
    return lambda proposed: word(proposed) == target
