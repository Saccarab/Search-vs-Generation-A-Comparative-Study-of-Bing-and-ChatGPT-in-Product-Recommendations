import numpy as np


def syntactic_overlap(l1: list, l2: list) -> float:
    """
    Compute the Szymkiewicz–Simpson coefficient (overlap coefficient)
    between two lists. Returns 0.0 if either list is None or empty.
    """
    s1 = set(l1)
    s2 = set(l2)
    
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    return len(s1 & s2) / min(len(s1), len(s2))


def semantic_overlap(l1: list, l2: list) -> float:
    pass