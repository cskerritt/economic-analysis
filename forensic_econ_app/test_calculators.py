import pytest
from calculators import calculate_worklife_factor_logic, calculate_aef_logic
from decimal import Decimal

def test_worklife_factor():
    result = calculate_worklife_factor_logic(20, 40)
    assert result == Decimal("50.00")

def test_aef_basic():
    df, factor = calculate_aef_logic(
        gross_earnings_base=100,
        worklife_adjustment=30,
        unemployment_factor=5,
        fringe_benefit=3,
        tax_liability=20,
        wrongful_death=False
    )
    assert factor > Decimal("0"), "AEF factor should be positive"
    assert factor < Decimal("100"), "AEF factor typically under 100"
