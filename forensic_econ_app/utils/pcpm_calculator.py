"""
Personal Consumption/Personal Maintenance Calculator Module.

This module implements Eric Christensen's 2022 methodology for computing
Personal Consumption (PC) or Personal Maintenance (PM) percentages.
"""

from typing import Dict, Tuple, Union
from decimal import Decimal

# Dictionary of Regression Coefficients
PCPM_COEFFS: Dict[Tuple[str, int, str, str], Dict[str, Tuple[float, float]]] = {
    # Men, 1-person
    ('male', 1, 'PC', 'high'):   {'interview': (314.942, -0.592683), 'diary': (52.983, -0.528152)},
    ('male', 1, 'PC', 'low'):    {'interview': (235.910, -0.579785), 'diary': (69.088, -0.555610)},
    ('male', 1, 'PM', 'high'):   {'interview': (364.815, -0.610834), 'diary': (38.018, -0.502998)},
    ('male', 1, 'PM', 'low'):    {'interview': (265.456, -0.595023), 'diary': (49.771, -0.530966)},

    # Men, 2-person
    ('male', 2, 'PC', 'high'):   {'interview': (26.768,  -0.515089), 'diary': (452.070, -0.881204)},
    ('male', 2, 'PC', 'low'):    {'interview': (33.911,  -0.554462), 'diary': (452.070, -0.881204)},
    ('male', 2, 'PM', 'high'):   {'interview': (31.796,  -0.533694), 'diary': (761.178, -0.935044)},
    ('male', 2, 'PM', 'low'):    {'interview': (42.678,  -0.579024), 'diary': (761.178, -0.935044)},

    # Men, 3-person
    ('male', 3, 'PC', 'high'):   {'interview': (3.732,   -0.361830), 'diary': (18.579,  -0.610521)},
    ('male', 3, 'PC', 'low'):    {'interview': (5.851,   -0.424854), 'diary': (18.579,  -0.610521)},
    ('male', 3, 'PM', 'high'):   {'interview': (4.399,   -0.379149), 'diary': (19.425,  -0.619607)},
    ('male', 3, 'PM', 'low'):    {'interview': (7.496,   -0.450484), 'diary': (19.425,  -0.619607)},

    # Men, 4-person
    ('male', 4, 'PC', 'high'):   {'interview': (12.086,  -0.476640), 'diary': (7.790,   -0.540042)},
    ('male', 4, 'PC', 'low'):    {'interview': (26.990,  -0.576067), 'diary': (7.790,   -0.540042)},
    ('male', 4, 'PM', 'high'):   {'interview': (14.646,  -0.496820), 'diary': (8.832,   -0.556018)},
    ('male', 4, 'PM', 'low'):    {'interview': (36.770,  -0.607973), 'diary': (8.832,   -0.556018)},

    # Men, 5+ person
    ('male', 5, 'PC', 'high'):   {'interview': (19.658,  -0.540293), 'diary': (11.405,  -0.592661)},
    ('male', 5, 'PC', 'low'):    {'interview': (11.725,  -0.522069), 'diary': (11.405,  -0.592661)},
    ('male', 5, 'PM', 'high'):   {'interview': (24.822,  -0.563766), 'diary': (12.187,  -0.603314)},
    ('male', 5, 'PM', 'low'):    {'interview': (16.141,  -0.554239), 'diary': (12.187,  -0.603314)},

    # Women, 1-person
    ('female', 1, 'PC', 'high'): {'interview': (87.362,  -0.466948), 'diary': (19.026,  -0.431771)},
    ('female', 1, 'PC', 'low'):  {'interview': (80.577,  -0.470534), 'diary': (19.333,  -0.433862)},
    ('female', 1, 'PM', 'high'): {'interview': (97.399,  -0.481773), 'diary': (17.899,  -0.432099)},
    ('female', 1, 'PM', 'low'):  {'interview': (89.788,  -0.485350), 'diary': (18.203,  -0.434306)},

    # Women, 2-person
    ('female', 2, 'PC', 'high'): {'interview': (19.707,  -0.476965), 'diary': (21.774,  -0.581075)},
    ('female', 2, 'PC', 'low'):  {'interview': (21.552,  -0.500580), 'diary': (21.774,  -0.581075)},
    ('female', 2, 'PM', 'high'): {'interview': (22.594,  -0.492073), 'diary': (24.828,  -0.597126)},
    ('female', 2, 'PM', 'low'):  {'interview': (25.624,  -0.519520), 'diary': (24.828,  -0.597126)},

    # Women, 3-person
    ('female', 3, 'PC', 'high'): {'interview': (3.207,   -0.337180), 'diary': (28.552,  -0.627990)},
    ('female', 3, 'PC', 'low'):  {'interview': (5.666,   -0.406188), 'diary': (28.552,  -0.627990)},
    ('female', 3, 'PM', 'high'): {'interview': (3.554,   -0.348881), 'diary': (26.674,  -0.625777)},
    ('female', 3, 'PM', 'low'):  {'interview': (6.605,   -0.423071), 'diary': (26.674,  -0.625777)},

    # Women, 4-person
    ('female', 4, 'PC', 'high'): {'interview': (5.139,   -0.390324), 'diary': (15.001,  -0.575602)},
    ('female', 4, 'PC', 'low'):  {'interview': (7.937,   -0.451890), 'diary': (15.001,  -0.575602)},
    ('female', 4, 'PM', 'high'): {'interview': (6.002,   -0.406818), 'diary': (16.953,  -0.590173)},
    ('female', 4, 'PM', 'low'):  {'interview': (9.933,   -0.475412), 'diary': (16.953,  -0.590173)},

    # Women, 5+ person
    ('female', 5, 'PC', 'high'): {'interview': (12.089,  -0.485617), 'diary': (13.540,  -0.580066)},
    ('female', 5, 'PC', 'low'):  {'interview': (8.653,   -0.479392), 'diary': (13.540,  -0.580066)},
    ('female', 5, 'PM', 'high'): {'interview': (14.756,  -0.505718), 'diary': (14.415,  -0.589079)},
    ('female', 5, 'PM', 'low'):  {'interview': (11.256,  -0.505885), 'diary': (14.415,  -0.589079)},
}

def _compute_single_estimate(income: float, sex: str, household_size: int, measure: str, estimate: str) -> float:
    """
    Internal helper that computes a single PC/PM estimate (either 'low' or 'high').
    """
    # Cap household size at 5
    household_size = min(household_size, 5)

    key = (sex, household_size, measure, estimate)
    if key not in PCPM_COEFFS:
        raise KeyError(f"No regression coefficients available for {key}.")

    coeff_data = PCPM_COEFFS[key]
    aI, bI = coeff_data['interview']
    aD, bD = coeff_data['diary']

    # Use the power-function approach
    return aI * (income ** bI) + aD * (income ** bD)

def get_pcpm_percentage(income: float,
                       sex: str,
                       household_size: int,
                       measure: str = 'PC',
                       estimate: str = 'high') -> float:
    """
    Calculate the personal consumption (PC%) or personal maintenance (PM%)
    as a percentage of total household income.

    Args:
        income: Annual household income in dollars (must be positive)
        sex: 'male' or 'female' (case-insensitive)
        household_size: Number of people in household (1-5, 5 means "5 or more")
        measure: 'PC' (Personal Consumption) or 'PM' (Personal Maintenance)
        estimate: 'low', 'high', or 'midpoint'

    Returns:
        float: Percentage (0-100) representing the fraction of household income
              that would be self-consumed by the adult decedent
    """
    # Normalize inputs
    sex = sex.lower().strip()
    measure = measure.upper().strip()
    estimate = estimate.lower().strip()
    
    # Validate inputs
    if income <= 0:
        raise ValueError("Income must be positive.")
    if sex not in ['male', 'female']:
        raise ValueError("sex must be 'male' or 'female'.")
    if household_size < 1:
        raise ValueError("household_size must be >= 1.")
    if measure not in ['PC', 'PM']:
        raise ValueError("measure must be 'PC' or 'PM'.")
    if estimate not in ['low', 'high', 'midpoint']:
        raise ValueError("estimate must be 'low', 'high', or 'midpoint'.")

    # For midpoint, compute average of low and high
    if estimate == 'midpoint':
        val_low = _compute_single_estimate(income, sex, household_size, measure, 'low')
        val_high = _compute_single_estimate(income, sex, household_size, measure, 'high')
        return 0.5 * (val_low + val_high)
    else:
        return _compute_single_estimate(income, sex, household_size, measure, estimate) 