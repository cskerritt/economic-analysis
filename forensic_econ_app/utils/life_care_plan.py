"""
Life Care Plan Calculator Module.

This module provides comprehensive functionality for generating life care plan tables
with extensive validations, multiple patterns of item occurrences, and detailed cost tracking.
"""

import math
import pandas as pd
from typing import List, Dict, Union
from decimal import Decimal

# Frequency mapping for different time periods
FREQ_MAP = {
    "annual": 1,
    "semiannual": 2,
    "quarterly": 4,
    "bimonthly": 6,
    "monthly": 12,
    "weekly": 52
}

def verify_inputs(
    start_year: int,
    start_age: float,
    duration_years: float,
    annual_discount_rate: float,
    items: list,
    frequency: str
) -> None:
    """
    Verify that all input parameters are within acceptable ranges.
    Raises ValueError if any check fails.
    """
    if start_year < 1900 or start_year > 2100:
        raise ValueError(f"start_year ({start_year}) is out of a typical valid range (1900–2100).")
    if start_age < 0 or start_age > 130:
        raise ValueError(f"start_age ({start_age:.2f}) is out of a typical valid range (0–130).")
    if duration_years < 0 or duration_years > 100:
        raise ValueError(f"duration_years ({duration_years}) is out of range (0–100).")
    if annual_discount_rate < -1.0 or annual_discount_rate > 1.0:
        raise ValueError(f"annual_discount_rate ({annual_discount_rate}) is not in [-1, 1].")
    if frequency not in FREQ_MAP:
        raise ValueError(f"Unsupported frequency: '{frequency}'. Must be one of {list(FREQ_MAP.keys())}.")

    for item in items:
        name = item.get("name", "Unnamed Item")
        base_cost = item.get("base_cost", 0)
        if base_cost < 0:
            raise ValueError(f"Item '{name}' has a negative base_cost ({base_cost}); not allowed.")
        growth_rate = item.get("growth_rate", 0)
        if growth_rate < -1.0 or growth_rate > 1.0:
            raise ValueError(
                f"Item '{name}' has a growth_rate ({growth_rate}) not in [-1, 1]."
            )
        pattern = item.get("pattern", "recurring")
        if pattern not in ["once", "interval", "recurring", "continuous"]:
            raise ValueError(
                f"Item '{name}' has unsupported pattern '{pattern}'. "
                "Must be one of: 'once', 'interval', 'recurring', or 'continuous'."
            )

def verify_dataframe(
    df: pd.DataFrame, 
    items: list,
    discounting_enabled: bool,
    debug: bool = False
) -> None:
    """
    Performs post-calculation checks on the final DataFrame:
      1. If discounting is enabled, check that discounted cost <= undiscounted cost for each row/item.
      2. Check that the final sum row(s) match column sums.
    Raises an AssertionError if any issue is found.
    """
    # 1. If discounting is enabled, ensure discounted <= undiscounted
    if discounting_enabled:
        for item in items:
            undisc_col = f"{item['name']} (Undiscounted)"
            disc_col   = f"{item['name']} (Discounted)"
            for idx, row in df.iterrows():
                # Skip summary rows that do not hold numeric data
                if isinstance(row[undisc_col], (int, float)) and isinstance(row[disc_col], (int, float)):
                    if row[disc_col] > row[undisc_col] + 1e-6:  # small float allowance
                        raise AssertionError(
                            f"Discounted value {row[disc_col]} exceeds Undiscounted {row[undisc_col]}"
                            f" at row index {idx} for item '{item['name']}'."
                        )

    # 2. Check that summary rows match the sums
    grand_total_idx = df.index[df['Age'] == "Grand TOTAL"].tolist()
    if len(grand_total_idx) == 0:
        if debug:
            print("No Grand TOTAL row found to verify.")
        return
    
    grand_total_idx = grand_total_idx[0]
    undiscounted_total_col = "Total (Undiscounted)"
    discounted_total_col = "Total (Discounted)"
    
    if undiscounted_total_col in df.columns and discounted_total_col in df.columns:
        # Convert values to numeric, coercing errors to NaN
        undisc_values = pd.to_numeric(df.loc[:grand_total_idx-1, undiscounted_total_col], errors='coerce')
        disc_values = pd.to_numeric(df.loc[:grand_total_idx-1, discounted_total_col], errors='coerce')
        
        # Sum only the numeric values
        actual_undisc_sum = undisc_values.sum()
        actual_disc_sum = disc_values.sum()

        reported_undisc = df.loc[grand_total_idx, undiscounted_total_col]
        reported_disc = df.loc[grand_total_idx, discounted_total_col]

        if isinstance(reported_undisc, str):
            reported_undisc = float(reported_undisc.replace(",", ""))
        if isinstance(reported_disc, str):
            reported_disc = float(reported_disc.replace(",", ""))

        if abs(actual_undisc_sum - reported_undisc) > 1e-3:
            raise AssertionError(
                f"Grand TOTAL (Undiscounted) mismatch: Expected ~{actual_undisc_sum:.2f}, "
                f"Found {reported_undisc:.2f}"
            )
        if abs(actual_disc_sum - reported_disc) > 1e-3:
            raise AssertionError(
                f"Grand TOTAL (Discounted) mismatch: Expected ~{actual_disc_sum:.2f}, "
                f"Found {reported_disc:.2f}"
            )

        if debug:
            print(f"Grand TOTAL verification OK. Undiscounted: {actual_undisc_sum:.2f}, "
                  f"Discounted: {actual_disc_sum:.2f}.")

def generate_life_care_plan_table(
    category_name: str,
    start_year: int,
    start_age: float,
    duration_years: float,
    items: list,
    annual_discount_rate: float = 0.03,
    discounting_enabled: bool = True,
    frequency: str = "annual",
    debug: bool = False
) -> pd.DataFrame:
    """
    Generates a comprehensive life care plan table with extensive validations,
    multiple patterns of item occurrences, separate Undiscounted and Discounted columns,
    and final summary rows. Allows sub-year frequencies (monthly, quarterly, etc.).
    """
    if debug:
        print("\nDEBUG: Life Care Plan Table Generation")
        print(f"Category: {category_name}")
        print(f"Start Year: {start_year}")
        print(f"Start Age: {start_age}")
        print(f"Duration Years: {duration_years}")
        print(f"Discount Rate: {annual_discount_rate}")
        print(f"Items: {items}")

    verify_inputs(start_year, start_age, duration_years, annual_discount_rate, items, frequency)

    periods_per_year = FREQ_MAP[frequency]
    total_periods = int(math.floor(duration_years * periods_per_year))
    fractional_part = (duration_years * periods_per_year) - total_periods

    if debug:
        print(f"\nDEBUG: Periods setup:")
        print(f"Periods per year: {periods_per_year}")
        print(f"Total periods: {total_periods}")
        print(f"Fractional part: {fractional_part}")

    period_tuples = []
    for p_idx in range(total_periods + 1):
        frac_yr = p_idx / float(periods_per_year)
        period_tuples.append((p_idx, frac_yr))

    if fractional_part > 1e-6:
        final_p_idx = total_periods + 1
        frac_yr = (total_periods + fractional_part) / float(periods_per_year)
        period_tuples.append((final_p_idx, frac_yr))

    rows = []
    item_totals_undiscounted = {it["name"]: 0.0 for it in items}
    item_totals_discounted = {it["name"]: 0.0 for it in items}

    for (p_idx, frac_yr) in period_tuples:
        cal_year = start_year + int(frac_yr)
        current_age = start_age + frac_yr

        row_data = {
            "Period Index": p_idx,
            "Calendar Year": cal_year,
            "Age": f"{current_age:.2f}"
        }

        if debug and p_idx == 0:
            print(f"\nDEBUG: First period details:")
            print(f"Period Index: {p_idx}")
            print(f"Calendar Year: {cal_year}")
            print(f"Current Age: {current_age}")

        for item in items:
            name = item["name"]
            base_cost = item["base_cost"]
            growth_rate = item.get("growth_rate", 0.0)
            pattern = item.get("pattern", "recurring").lower()
            quantity_per_period = item.get("quantity_per_period", 1.0)
            year_offset = item.get("year_offset", 0.0)
            repeat_interval = item.get("repeat_interval", 1.0)

            if debug and p_idx == 0:
                print(f"\nDEBUG: Processing item {name} in first period:")
                print(f"Base Cost: {base_cost}")
                print(f"Growth Rate: {growth_rate}")
                print(f"Pattern: {pattern}")
                print(f"Year Offset: {year_offset}")

            applies = False
            if pattern in ["recurring", "continuous"]:
                applies = True
            elif pattern == "once":
                if math.isclose(frac_yr, year_offset, abs_tol=1e-5):
                    applies = True
            elif pattern == "interval":
                if frac_yr >= year_offset - 1e-9:
                    intervals_passed = (frac_yr - year_offset) / repeat_interval
                    if intervals_passed >= -1e-9:
                        if abs(intervals_passed - round(intervals_passed)) < 1e-5:
                            applies = True

            if debug and p_idx == 0:
                print(f"Applies in first period: {applies}")

            if not applies:
                row_data[name + " (Undiscounted)"] = 0.00
                row_data[name + " (Discounted)"] = 0.00
                continue

            grown_cost = base_cost * ((1 + growth_rate)**frac_yr)
            undiscounted_cost = grown_cost * quantity_per_period

            if discounting_enabled:
                discounted_cost = undiscounted_cost / ((1 + annual_discount_rate)**frac_yr)
            else:
                discounted_cost = undiscounted_cost

            if debug and p_idx == 0:
                print(f"Grown Cost: {grown_cost}")
                print(f"Undiscounted Cost: {undiscounted_cost}")
                print(f"Discounted Cost: {discounted_cost}")

            undc_rounded = round(undiscounted_cost, 2)
            disc_rounded = round(discounted_cost, 2)

            row_data[name + " (Undiscounted)"] = undc_rounded
            row_data[name + " (Discounted)"] = disc_rounded

            item_totals_undiscounted[name] += undc_rounded
            item_totals_discounted[name] += disc_rounded

        rows.append(row_data)

    df = pd.DataFrame(rows)

    # Add total columns
    undiscounted_cols = [f"{it['name']} (Undiscounted)" for it in items]
    discounted_cols = [f"{it['name']} (Discounted)" for it in items]
    df["Total (Undiscounted)"] = df[undiscounted_cols].sum(axis=1)
    df["Total (Discounted)"] = df[discounted_cols].sum(axis=1)

    if debug:
        print("\nDEBUG: Item Totals:")
        for name in item_totals_undiscounted:
            print(f"{name}:")
            print(f"  Undiscounted: {item_totals_undiscounted[name]}")
            print(f"  Discounted: {item_totals_discounted[name]}")

    # Add summary rows
    for item in items:
        name = item["name"]
        new_row = {col: "" for col in df.columns}
        new_row["Age"] = f"{name} TOTAL"
        new_row["Period Index"] = ""
        new_row["Calendar Year"] = ""
        new_row[f"{name} (Undiscounted)"] = f"{item_totals_undiscounted[name]:,.2f}"
        new_row[f"{name} (Discounted)"] = f"{item_totals_discounted[name]:,.2f}"
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Add grand total row
    new_row = {col: "" for col in df.columns}
    new_row["Age"] = "Grand TOTAL"
    new_row["Period Index"] = ""
    new_row["Calendar Year"] = ""
    total_undisc = sum(item_totals_undiscounted.values())
    total_disc = sum(item_totals_discounted.values())
    new_row["Total (Undiscounted)"] = f"{total_undisc:,.2f}"
    new_row["Total (Discounted)"] = f"{total_disc:,.2f}"
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    if debug:
        print("\nDEBUG: Grand Totals:")
        print(f"Total Undiscounted: {total_undisc}")
        print(f"Total Discounted: {total_disc}")

    verify_dataframe(df, items, discounting_enabled=discounting_enabled, debug=debug)

    return df 