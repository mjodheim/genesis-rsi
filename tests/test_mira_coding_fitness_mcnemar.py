import pytest

from genesis.mira_coding_fitness import mcnemar_exact_pvalue

@pytest.mark.parametrize(("b", "c"), [(1, 4), (4, 1)])
def test_mcnemar_exact_pvalue_two_sided(b, c):
    assert mcnemar_exact_pvalue(b, c) == 0.375
