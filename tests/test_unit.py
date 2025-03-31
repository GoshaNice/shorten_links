import pytest

from links.router import generate_random_code


@pytest.mark.parametrize(
    "length",
    [6, 7, 8, 9],
)
def test_generate_random_code_length(length):
    code = generate_random_code(length)
    assert len(code) == length
    assert all(c.isdigit() or c.isalpha() for c in code)
