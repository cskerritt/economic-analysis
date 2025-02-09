from decimal import Decimal, getcontext, ROUND_HALF_UP
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

def calculate_worklife_factor_logic(wle_years: float, yfs_years: float):
    """
    (WLE / YFS) * 100, returns None if yfs=0.
    """
    if yfs_years == 0:
        return None
    wle_dec = Decimal(str(wle_years))
    yfs_dec = Decimal(str(yfs_years))
    factor = (wle_dec / yfs_dec) * Decimal("100")
    return factor.quantize(Decimal("0.00"))

def calculate_aef_logic(
    gross_earnings_base: float,
    worklife_adjustment: float,
    unemployment_factor: float,
    fringe_benefit: float,
    tax_liability: float,
    wrongful_death: bool = False,
    personal_type: str = "",
    personal_percentage: float = 0.0
):
    """
    Returns (DataFrame of steps, final AEF as Decimal).
    """
    GE = Decimal(str(gross_earnings_base))
    WLA = Decimal(str(worklife_adjustment)) / Decimal("100")
    UF = Decimal(str(unemployment_factor)) / Decimal("100")
    FB = Decimal(str(fringe_benefit)) / Decimal("100")
    TL = Decimal(str(tax_liability)) / Decimal("100")
    PC = Decimal(str(personal_percentage)) / Decimal("100") if wrongful_death else Decimal("0")

    base_adjustment = GE * WLA * (Decimal("1") - UF)
    fringe_adjusted = base_adjustment * (Decimal("1") + FB)
    tax_adjustment = base_adjustment * TL
    final_adjusted = (fringe_adjusted - tax_adjustment) * (Decimal("1") - PC)

    total_factor = (final_adjusted / GE) * Decimal("100")
    total_factor = total_factor.quantize(Decimal("0.00"))

    steps = []
    steps.append(("Gross Earnings Base", "100.00%"))
    steps.append(("x WorkLife Adjustment", f"{worklife_adjustment:.2f}%"))
    steps.append(("x (1 - Unemployment Factor)", f"{100 - unemployment_factor:.2f}%"))
    steps.append(("= Adjusted Base Earnings", f"{base_adjustment.quantize(Decimal('0.00'))}%"))
    steps.append(("x (1 - Tax Liability)", f"{100 - tax_liability:.2f}%"))
    steps.append(("x (1 + Fringe Benefit)", f"{100 + fringe_benefit:.2f}%"))

    if wrongful_death and personal_percentage > 0:
        steps.append((
            "x (1 - Personal Maintenance/Consumption)",
            f"{(Decimal('100') - Decimal(str(personal_percentage))):.2f}% ({personal_type})"
        ))

    steps.append(("= Fringe Benefits/Tax Adjusted Base", f"{fringe_adjusted.quantize(Decimal('0.00'))}%"))
    steps.append(("AEF (Adjusted Earnings Factor)", f"{total_factor}%"))

    df = pd.DataFrame({"Step": [s[0] for s in steps], "Value": [s[1] for s in steps]})
    return df, total_factor

def compute_earnings_table(
    start_date: datetime,
    end_date: datetime,
    wage_base: Decimal,
    residual_base: Decimal,
    growth_rate: float,
    discount_rate: float,
    adjustment_factor: float,
    date_of_birth: datetime = None,
    reference_start: datetime = None
):
    """
    Return (DataFrame, final_wage_base, final_residual_base).
    Demonstrates partial-year calculation with day-based approach.
    """
    if end_date < start_date:
        return pd.DataFrame(), Decimal("0"), Decimal("0")

    if not reference_start:
        reference_start = start_date

    g_dec = Decimal(str(growth_rate)) / Decimal("100")
    d_dec = Decimal(str(discount_rate)) / Decimal("100")
    adj_dec = Decimal(str(adjustment_factor)) / Decimal("100")

    records = {
        "Year": [],
        "Age": [],
        "PortionOfYear": [],
        "WageBase": [],
        "GrossEarnings": [],
        "AdjustedEarnings": [],
        "PresentValue": []
    }

    current_wb = wage_base
    current_rb = residual_base
    seg_start = start_date
    cyear = start_date.year

    while True:
        year_start = datetime(year=cyear, month=1, day=1)
        if year_start < seg_start:
            year_start = seg_start
        year_end = datetime(year=cyear, month=12, day=31)
        if year_end > end_date:
            year_end = end_date
        if year_start > year_end:
            break

        days_in_segment = (year_end - year_start).days + 1
        if days_in_segment < 1:
            break

        portion = Decimal(str(days_in_segment)) / Decimal("365.25")

        # Age
        if date_of_birth:
            age_this_year = relativedelta(year_start, date_of_birth).years
        else:
            age_this_year = ""

        net_base = current_wb - current_rb
        if net_base < 0:
            net_base = Decimal("0")

        gross_earnings = net_base * portion
        adjusted_earnings = gross_earnings * adj_dec

        yrs_from_ref = Decimal(str((year_start - reference_start).days)) / Decimal("365.25")
        # discounting
        present_value = adjusted_earnings / ((Decimal("1") + d_dec) ** yrs_from_ref)

        records["Year"].append(str(cyear))
        records["Age"].append(str(age_this_year))
        records["PortionOfYear"].append(f"{portion:.4f}")
        records["WageBase"].append(f"{net_base.quantize(Decimal('0.00'))}")
        records["GrossEarnings"].append(f"{gross_earnings.quantize(Decimal('0.00'))}")
        records["AdjustedEarnings"].append(f"{adjusted_earnings.quantize(Decimal('0.00'))}")
        records["PresentValue"].append(f"{present_value.quantize(Decimal('0.00'))}")

        current_wb *= (Decimal("1") + g_dec)
        current_rb *= (Decimal("1") + g_dec)

        if year_end == end_date:
            return pd.DataFrame(records), current_wb, current_rb

        cyear += 1
        seg_start = year_end
        seg_start += relativedelta(days=1)
