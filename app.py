# app.py
"""
Single-file Flask app demonstrating:
  1) Evaluee creation/selection (name, state, discounting flag)
  2) Demographics step (anchored to Date of Injury)
  3) Worklife Factor Calculator
  4) AEF Calculator (clearer wrongful death box)
  5) Earnings Calculator with multi-scenario discount/growth,
     skipping discount if user indicated no discounting.

Storing evaluees in-memory so we can revisit them by evaluee_id.
"""

import logging
import os
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Optional, Tuple

import pandas as pd
from flask import (
    Flask, request, render_template_string, send_file,
    flash, redirect, url_for, session
)

# ---------------------------------------------------------------------
#                        FLASK CONFIG
# ---------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = "ReplaceWithASecretKeyInProduction"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# decimal config
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# ---------------------------------------------------------------------
#                   IN-MEMORY DATA STRUCTURES
# ---------------------------------------------------------------------

# We'll store all Evaluees in a dict:
#   EVALUEES[evaluee_id] = {
#       "first_name": ...,
#       "last_name": ...,
#       "state": ...,
#       "uses_discounting": True/False,
#       "discount_rates": [3.0, 5.0, 7.0],  # or [0.0] if discounting is not used
#       ...
#   }
EVALUEES = {}

# We'll keep other data (demographics, etc.) inside each evaluee entry
# to let us revisit it later.

# ---------------------------------------------------------------------
#                           HELPERS
# ---------------------------------------------------------------------

def parse_mdy(date_str: str) -> Optional[datetime]:
    """Parses MM/DD/YYYY. Returns None if invalid/empty."""
    if not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), "%m/%d/%Y")
    except ValueError:
        return None

def add_decimal_years(base_date: datetime, decimal_years: Decimal) -> datetime:
    """Adds decimal years to a date (e.g. 25.5 => 25 years + ~6 months)."""
    whole_years = int(decimal_years)
    fraction = decimal_years - whole_years
    months = int(round(fraction * Decimal("12")))
    return base_date + relativedelta(years=whole_years, months=months)

def format_currency(value: Decimal) -> str:
    return f"${value:,.2f}"

def format_percentage(value: Decimal) -> str:
    return f"{value:,.2f}%"

def sum_currency_column(values) -> Decimal:
    total = Decimal("0")
    for v in values:
        clean = v.replace("$", "").replace(",", "")
        total += Decimal(clean)
    return total

# ---------------------------------------------------------------------
#                  0) MANAGE EVALUEE (CREATE / SELECT)
# ---------------------------------------------------------------------

START_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Start / Manage Evaluee</title>
</head>
<body>
<h1>Create or Select an Evaluee</h1>

{% with messages = get_flashed_messages() %}
{% if messages %}
  <ul>
  {% for msg in messages %}
    <li>{{ msg }}</li>
  {% endfor %}
  </ul>
{% endif %}
{% endwith %}

<form method="POST" action="{{ url_for('create_evaluee') }}">
  <fieldset>
    <legend>New Evaluee</legend>
    <label>First Name: <input type="text" name="first_name" required></label><br><br>
    <label>Last Name: <input type="text" name="last_name" required></label><br><br>
    <label>State (Jurisdiction): <input type="text" name="state" required></label><br><br>
    <label>Use Discounting?
      <input type="checkbox" name="discounting" value="yes">
    </label><br><br>
    <label>Default Discount Rates (comma-separated):
      <input type="text" name="discount_rates" value="3,5,7">
    </label>
    <p><small>If discounting is NOT used, we will automatically set discount rates to 0.0</small></p>
    <button type="submit">Create Evaluee</button>
  </fieldset>
</form>

<hr>
<h2>Existing Evaluees</h2>
{% if evaluees %}
  <ul>
    {% for k, v in evaluees.items() %}
      <li>
        {{ v.first_name }} {{ v.last_name }} (State: {{ v.state }}) - 
        [ <a href="{{ url_for('home', evaluee_id=k) }}">Select</a> ]
      </li>
    {% endfor %}
  </ul>
{% else %}
  <p>No evaluees created yet.</p>
{% endif %}

</body>
</html>
"""

@app.route("/", methods=["GET"])
def start():
    """Displays form to create a new Evaluee and lists existing ones."""
    return render_template_string(START_TEMPLATE, evaluees=EVALUEES)

@app.route("/create_evaluee", methods=["POST"])
def create_evaluee():
    """Creates an evaluee in memory, storing discount usage, name, state, etc."""
    from time import time
    f_name = request.form.get("first_name", "").strip()
    l_name = request.form.get("last_name", "").strip()
    state = request.form.get("state", "").strip()
    discounting = ("discounting" in request.form and request.form["discounting"] == "yes")
    discount_rates_str = request.form.get("discount_rates", "").strip()

    if not f_name or not l_name or not state:
        flash("Missing required fields.")
        return redirect(url_for("start"))

    # If discounting is false, we won't store any rates except 0.0.
    if not discounting:
        final_rates = [0.0]
    else:
        if discount_rates_str:
            try:
                final_rates = [float(x) for x in discount_rates_str.split(",") if x.strip()]
            except ValueError:
                flash("Invalid discount rates. Example: 3,5,7")
                return redirect(url_for("start"))
        else:
            final_rates = [3.0, 5.0, 7.0]  # default fallback

    e_id = f"eval_{time()}"
    EVALUEES[e_id] = {
        "first_name": f_name,
        "last_name": l_name,
        "state": state,
        "uses_discounting": discounting,
        "discount_rates": final_rates,
        # We'll add more data from the other calculators as we go
    }
    flash("Evaluee created successfully.")
    return redirect(url_for("home", evaluee_id=e_id))


HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Evaluee Home</title>
</head>
<body>
<h1>Welcome, {{ evaluee.first_name }} {{ evaluee.last_name }}</h1>
<p>State (Jurisdiction): {{ evaluee.state }}</p>
<p>Uses Discounting: {{ 'Yes' if evaluee.uses_discounting else 'No' }}</p>
<p>Current Discount Rates: {{ evaluee.discount_rates }}</p>

<p>Select a tool:</p>
<ul>
  <li><a href="{{ url_for('demographics_form', evaluee_id=evaluee_id) }}">Demographics (Anchored at Date of Injury)</a></li>
  <li><a href="{{ url_for('worklife_form', evaluee_id=evaluee_id) }}">Worklife Factor Calculator</a></li>
  <li><a href="{{ url_for('aef_form', evaluee_id=evaluee_id) }}">AEF Calculator</a></li>
  <li><a href="{{ url_for('earnings_form', evaluee_id=evaluee_id) }}">Earnings Calculator (Multi-Scenario)</a></li>
</ul>

<p><a href="{{ url_for('start') }}">Back to Main Start</a></p>
</body>
</html>
"""

@app.route("/home/<evaluee_id>", methods=["GET"])
def home(evaluee_id):
    """Displays a home page with links to all calculators for this Evaluee."""
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))
    evaluee = EVALUEES[evaluee_id]
    return render_template_string(HOME_TEMPLATE, evaluee_id=evaluee_id, evaluee=evaluee)

# ---------------------------------------------------------------------
#          1) DEMOGRAPHICS (ANCHOR AT DATE OF INJURY)
# ---------------------------------------------------------------------

DEMOGRAPHICS_FORM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Demographics</title>
</head>
<body>
<h1>Demographics / Preliminary Calculations</h1>
<p>Evaluee: {{ evaluee.first_name }} {{ evaluee.last_name }} | State: {{ evaluee.state }}</p>

<p>Enter Date of Birth, Date of Injury, and decimal years for Life Expectancy,
 Work Life Expectancy, and Years to Final Separation.
 <strong>All anchored at the Date of Injury.</strong></p>

{% with messages = get_flashed_messages() %}
{% if messages %}
  <ul>
  {% for msg in messages %}
    <li>{{ msg }}</li>
  {% endfor %}
  </ul>
{% endif %}
{% endwith %}

<form method="POST" action="{{ url_for('demographics_submit', evaluee_id=evaluee_id) }}">
  <label>Date of Birth (MM/DD/YYYY): <input type="text" name="dob" required></label><br><br>
  <label>Date of Injury (MM/DD/YYYY): <input type="text" name="doi" required></label><br><br>
  <label>Life Expectancy (decimal years from Injury): 
      <input type="number" step="0.01" name="life_exp" required>
  </label><br><br>
  <label>Work Life Expectancy (decimal years from Injury):
      <input type="number" step="0.01" name="wle" required>
  </label><br><br>
  <label>Years to Final Separation (decimal years from Injury):
      <input type="number" step="0.01" name="yfs" required>
  </label><br><br>

  <button type="submit">Compute Demographics</button>
</form>

<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Back</a></p>
</body>
</html>
"""

DEMOGRAPHICS_RESULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Demographics Result</title>
</head>
<body>
<h1>Demographics Result for {{ evaluee.first_name }} {{ evaluee.last_name }}</h1>
<p>State (Jurisdiction): {{ evaluee.state }}</p>

<p>Date of Birth: {{ dob_str }}<br>
Date of Injury: {{ doi_str }}<br>
Age at Injury: {{ age_injury }} years</p>

<hr>
<p>Life Expectancy (from Injury): {{ life_exp }} years</p>
<p>Work Life Expectancy (from Injury): {{ wle }} years</p>
<p>Years to Final Separation (from Injury): {{ yfs }} years</p>
<hr>

<p>Anticipated Date of Death: {{ death_date_str }}</p>
<p>Statistical Retirement Date: {{ retirement_date_str }}</p>
<p>Statistical Date of Separation: {{ separation_date_str }}</p>

<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Back to Home</a></p>
</body>
</html>
"""

@app.route("/demographics/<evaluee_id>", methods=["GET"])
def demographics_form(evaluee_id):
    """Form to input demographics (DOB, DOI, etc.) for a given evaluee."""
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))
    evaluee = EVALUEES[evaluee_id]
    return render_template_string(DEMOGRAPHICS_FORM_TEMPLATE, evaluee_id=evaluee_id, evaluee=evaluee)

@app.route("/demographics_submit/<evaluee_id>", methods=["POST"])
def demographics_submit(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))

    form = request.form
    dob_str = form.get("dob", "")
    doi_str = form.get("doi", "")
    life_exp_str = form.get("life_exp", "0")
    wle_str = form.get("wle", "0")
    yfs_str = form.get("yfs", "0")

    dob_dt = parse_mdy(dob_str)
    doi_dt = parse_mdy(doi_str)
    if not dob_dt or not doi_dt:
        flash("Invalid date format. Use MM/DD/YYYY.")
        return redirect(url_for("demographics_form", evaluee_id=evaluee_id))

    try:
        life_exp = Decimal(str(float(life_exp_str)))
        wle = Decimal(str(float(wle_str)))
        yfs = Decimal(str(float(yfs_str)))
    except ValueError as e:
        flash(f"Invalid numeric input: {e}")
        return redirect(url_for("demographics_form", evaluee_id=evaluee_id))

    # Age at injury
    age_injury = relativedelta(doi_dt, dob_dt).years

    # 1) Death = Injury + Life Exp
    death_date = add_decimal_years(doi_dt, life_exp)
    # 2) Retirement = Injury + WLE
    retirement_date = add_decimal_years(doi_dt, wle)
    # 3) Separation = Injury + yfs
    separation_date = add_decimal_years(doi_dt, yfs)

    def fmt_date(d): return d.strftime("%m/%d/%Y")

    # Store in evaluee dictionary
    evaluee = EVALUEES[evaluee_id]
    evaluee["dob"] = dob_dt
    evaluee["doi"] = doi_dt
    evaluee["life_exp"] = life_exp
    evaluee["wle"] = wle
    evaluee["yfs"] = yfs
    evaluee["death_date"] = death_date
    evaluee["retirement_date"] = retirement_date
    evaluee["separation_date"] = separation_date

    return render_template_string(
        DEMOGRAPHICS_RESULT_TEMPLATE,
        evaluee_id=evaluee_id,
        evaluee=evaluee,
        dob_str=dob_str,
        doi_str=doi_str,
        age_injury=age_injury,
        life_exp=life_exp_str,
        wle=wle_str,
        yfs=yfs_str,
        death_date_str=fmt_date(death_date),
        retirement_date_str=fmt_date(retirement_date),
        separation_date_str=fmt_date(separation_date)
    )

# ---------------------------------------------------------------------
#          2) WORKLIFE FACTOR CALCULATOR
# ---------------------------------------------------------------------

WORKLIFE_FORM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Worklife Factor</title>
</head>
<body>
<h1>Worklife Factor Calculator</h1>
<p>Evaluee: {{ evaluee.first_name }} {{ evaluee.last_name }} | State: {{ evaluee.state }}</p>

{% with messages = get_flashed_messages() %}
{% if messages %}
  <ul>
  {% for msg in messages %}
    <li>{{ msg }}</li>
  {% endfor %}
  </ul>
{% endif %}
{% endwith %}

<form method="POST" action="{{ url_for('worklife_submit', evaluee_id=evaluee_id) }}">
  <label>Worklife Expectancy (Years): <input type="number" step="0.01" name="wle" required></label><br><br>
  <label>Years to Final Separation (YFS): <input type="number" step="0.01" name="yfs" required></label><br><br>
  <button type="submit">Calculate</button>
</form>

<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Back</a></p>
</body>
</html>
"""

WORKLIFE_RESULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Worklife Factor Result</title>
</head>
<body>
<h1>Worklife Factor Result for {{ evaluee.first_name }} {{ evaluee.last_name }}</h1>
<p>Worklife Factor: 
{% if factor is not none %}
  {{ factor }}%
{% else %}
  Invalid input or YFS=0
{% endif %}
</p>

<p><a href="{{ url_for('worklife_form', evaluee_id=evaluee_id) }}">Back</a></p>
<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Home</a></p>
</body>
</html>
"""

def calculate_worklife_factor_logic(wle_years: float, yfs_years: float) -> Optional[Decimal]:
    if yfs_years == 0:
        return None
    wle_dec = Decimal(str(wle_years))
    yfs_dec = Decimal(str(yfs_years))
    factor = (wle_dec / yfs_dec) * Decimal("100")
    return factor.quantize(Decimal("0.00"))

@app.route("/worklife/<evaluee_id>", methods=["GET"])
def worklife_form(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))
    evaluee = EVALUEES[evaluee_id]
    return render_template_string(WORKLIFE_FORM_TEMPLATE, evaluee_id=evaluee_id, evaluee=evaluee)

@app.route("/worklife_submit/<evaluee_id>", methods=["POST"])
def worklife_submit(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))

    wle = float(request.form.get("wle", 0))
    yfs = float(request.form.get("yfs", 0))

    factor = calculate_worklife_factor_logic(wle, yfs)
    evaluee = EVALUEES[evaluee_id]
    return render_template_string(WORKLIFE_RESULT_TEMPLATE, factor=factor, evaluee_id=evaluee_id, evaluee=evaluee)

# ---------------------------------------------------------------------
#          3) AEF CALCULATOR (Clearer Wrongful Death UI)
# ---------------------------------------------------------------------

AEF_FORM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AEF Calculator</title>
    <script>
    // Simple JS to show/hide personal fields if "Wrongful Death" is checked
    function togglePersonalFields() {
      var wdCheckbox = document.getElementById("wdCheck");
      var personalFields = document.getElementById("personalFields");
      if (wdCheckbox.checked) {
        personalFields.style.display = "block";
      } else {
        personalFields.style.display = "none";
      }
    }
    </script>
</head>
<body>
<h1>AEF Calculator</h1>
<p>Evaluee: {{ evaluee.first_name }} {{ evaluee.last_name }} | State: {{ evaluee.state }}</p>

{% with messages = get_flashed_messages() %}
{% if messages %}
  <ul>
  {% for msg in messages %}
    <li>{{ msg }}</li>
  {% endfor %}
  </ul>
{% endif %}
{% endwith %}

<form method="POST" action="{{ url_for('aef_submit', evaluee_id=evaluee_id) }}">
  <label>Gross Earnings Base (e.g., 100 for 100%): 
      <input type="number" step="0.01" name="gross_base" value="100.0" required>
  </label><br><br>
  <label>Worklife Adjustment (%): 
      <input type="number" step="0.01" name="wla" required>
  </label><br><br>
  <label>Unemployment Factor (%): 
      <input type="number" step="0.01" name="uf" required>
  </label><br><br>
  <label>Fringe Benefit (%): 
      <input type="number" step="0.01" name="fb" required>
  </label><br><br>
  <label>Tax Liability (%): 
      <input type="number" step="0.01" name="tl" required>
  </label><br><br>

  <label>
    <input type="checkbox" name="wrongful_death" value="yes" id="wdCheck" onclick="togglePersonalFields()">
    Is this a Wrongful Death matter?
  </label><br><br>

  <!-- Hidden field set for personal maintenance/consumption -->
  <div id="personalFields" style="display: none;">
    <label>Personal Type (e.g. maintenance or consumption): 
      <input type="text" name="personal_type">
    </label><br><br>
    <label>Personal Percentage (%): 
      <input type="number" step="0.01" name="personal_percentage" value="0.0">
    </label><br><br>
  </div>

  <button type="submit">Calculate AEF</button>
</form>

<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Back</a></p>
</body>
</html>
"""

AEF_RESULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AEF Calculation Result</title>
</head>
<body>
<h1>AEF Calculation Result for {{ evaluee.first_name }} {{ evaluee.last_name }}</h1>
<p>State: {{ evaluee.state }}</p>

<p>Final AEF: {{ final_aef }}%</p>
<br>
<table border="1" cellpadding="4" cellspacing="0">
  <tr>
    <th>Step</th>
    <th>Value</th>
  </tr>
  {% for i, row in df.iterrows() %}
  <tr>
    <td>{{ row['Step'] }}</td>
    <td>{{ row['Value'] }}</td>
  </tr>
  {% endfor %}
</table>

<p><a href="{{ url_for('aef_form', evaluee_id=evaluee_id) }}">Back</a></p>
<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Home</a></p>
</body>
</html>
"""

def calculate_aef_logic(
    gross_earnings_base: float,
    worklife_adjustment: float,
    unemployment_factor: float,
    fringe_benefit: float,
    tax_liability: float,
    wrongful_death: bool = False,
    personal_type: str = "",
    personal_percentage: float = 0.0
) -> Tuple[pd.DataFrame, Decimal]:
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

    steps = [
        ("Gross Earnings Base", "100.00%"),
        ("x WorkLife Adjustment", format_percentage(Decimal(str(worklife_adjustment)))),
        ("x (1 - Unemployment Factor)", format_percentage(Decimal("100") - Decimal(str(unemployment_factor)))),
        ("= Adjusted Base Earnings", format_percentage(base_adjustment.quantize(Decimal("0.00")))),
        ("x (1 - Tax Liability)", format_percentage(Decimal("100") - Decimal(str(tax_liability)))),
        ("x (1 + Fringe Benefit)", format_percentage(Decimal("100") + Decimal(str(fringe_benefit)))),
    ]
    if wrongful_death and personal_percentage > 0:
        steps.append((
            "x (1 - Personal Maintenance/Consumption)",
            f"{(Decimal('100') - Decimal(str(personal_percentage))):.2f}% ({personal_type.capitalize() or 'N/A'})"
        ))
    steps.append(
        ("= Fringe Benefits/Tax Adjusted Base", format_percentage(fringe_adjusted.quantize(Decimal("0.00"))))
    )
    steps.append(("AEF (Adjusted Earnings Factor)", format_percentage(total_factor)))

    df = pd.DataFrame({"Step": [s[0] for s in steps], "Value": [s[1] for s in steps]})
    return df, total_factor

@app.route("/aef/<evaluee_id>", methods=["GET"])
def aef_form(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))
    evaluee = EVALUEES[evaluee_id]
    return render_template_string(AEF_FORM_TEMPLATE, evaluee_id=evaluee_id, evaluee=evaluee)

@app.route("/aef_submit/<evaluee_id>", methods=["POST"])
def aef_submit(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))
    evaluee = EVALUEES[evaluee_id]

    try:
        gross_base = float(request.form["gross_base"])
        wla = float(request.form["wla"])
        uf = float(request.form["uf"])
        fb = float(request.form["fb"])
        tl = float(request.form["tl"])
        wd = ("wrongful_death" in request.form and request.form["wrongful_death"] == "yes")
        personal_type = request.form.get("personal_type", "").strip()
        personal_percentage = float(request.form.get("personal_percentage", 0))

        df, final_aef = calculate_aef_logic(
            gross_earnings_base=gross_base,
            worklife_adjustment=wla,
            unemployment_factor=uf,
            fringe_benefit=fb,
            tax_liability=tl,
            wrongful_death=wd,
            personal_type=personal_type,
            personal_percentage=personal_percentage
        )
        return render_template_string(AEF_RESULT_TEMPLATE,
                                      evaluee_id=evaluee_id,
                                      evaluee=evaluee,
                                      df=df,
                                      final_aef=final_aef)
    except ValueError as e:
        flash(f"Invalid numeric input: {e}")
        return redirect(url_for("aef_form", evaluee_id=evaluee_id))

# ---------------------------------------------------------------------
#          4) EARNINGS CALCULATOR (Multi-Scenario, skip discount if false)
# ---------------------------------------------------------------------

EARNINGS_FORM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Earnings Calculator</title>
</head>
<body>
<h1>Earnings Calculator (Multi-Scenario)</h1>
<p>Evaluee: {{ evaluee.first_name }} {{ evaluee.last_name }} | State: {{ evaluee.state }}</p>
<p>Uses Discounting: {{ 'Yes' if evaluee.uses_discounting else 'No' }}</p>
<p>Discount Rates: {{ evaluee.discount_rates }}</p>

<p>This calculator will use the 'Statistical Retirement Date' from Demographics if available,
 anchored at Date of Injury + Work Life Expectancy. If not set, it falls back to
 (Date of Report + WLE).</p>

{% with messages = get_flashed_messages() %}
{% if messages %}
  <ul>
  {% for msg in messages %}
    <li>{{ msg }}</li>
  {% endfor %}
  </ul>
{% endif %}
{% endwith %}

<form method="POST" action="{{ url_for('earnings_submit', evaluee_id=evaluee_id) }}">
    <fieldset>
        <legend>Claimant / Evaluee Information</legend>
        <label>Date of Birth (MM/DD/YYYY) <small>Optional if Demographics done</small>:
            <input type="text" name="date_of_birth">
        </label><br><br>
        <label>Date of Injury (MM/DD/YYYY) <small>Optional if Demographics done</small>:
            <input type="text" name="date_of_injury">
        </label><br><br>
        <label>Date of Report (MM/DD/YYYY):
            <input type="text" name="date_of_report" required>
        </label><br><br>
        <label>Work Life Expectancy (Years) <small>fallback if no Demographics</small>:
            <input type="number" step="0.01" name="worklife_years" value="{{ default_wle }}">
        </label><br><br>
    </fieldset>

    <fieldset>
        <legend>Financial Inputs</legend>
        <label>Starting Wage Base:
            <input type="number" step="0.01" name="starting_wage_base" 
                   value="{{ default_swb }}">
        </label><br><br>
        <label>Residual Earning Capacity:
            <input type="number" step="0.01" name="residual_earning_capacity"
                   value="{{ default_rec }}">
        </label><br><br>
        <label>Adjusted Earnings Factor (%):
            <input type="number" step="0.01" name="adjusted_earnings_factor"
                   value="{{ default_aef }}">
        </label><br><br>
    </fieldset>

    <p>
    <small>
    Since this Evaluee has discounting = {{ 'ON' if evaluee.uses_discounting else 'OFF' }},
    we will use the discount rates: {{ evaluee.discount_rates }} 
    (If OFF, discount rates = [0.0])
    </small>
    </p>

    <button type="submit">Compute Earnings</button>
</form>

<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Back</a></p>
</body>
</html>
"""

EARNINGS_RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Earnings Results</title>
</head>
<body>
<h1>Earnings Results for {{ evaluee.first_name }} {{ evaluee.last_name }}</h1>
<p>State: {{ evaluee.state }} | Using Retirement Date: {{ final_ret_date_str }}</p>

<p>Scenarios Computed: {{ scenarios|length }}</p>
<table border="1" cellpadding="4" cellspacing="0">
  <tr>
    <th>Scenario #</th>
    <th>Discount Rate</th>
    <th>Growth Rate</th>
    <th>Total Pre-Injury PV</th>
    <th>Total Post-Injury PV</th>
  </tr>
  {% for i, s in enumerate(scenarios) %}
  <tr>
    <td>{{ i+1 }}</td>
    <td>{{ s.discount_rate }}%</td>
    <td>{{ s.growth_rate }}%</td>
    <td>{{ s.pre_pv }}</td>
    <td>{{ s.post_pv }}</td>
  </tr>
  {% endfor %}
</table>

<p>
  <a href="{{ url_for('download_excel', evaluee_id=evaluee_id, key=eval_key) }}">Download Excel with All Scenarios</a>
</p>
<p><a href="{{ url_for('home', evaluee_id=evaluee_id) }}">Home</a></p>
</body>
</html>
"""

def compute_present_value(amount: Decimal, discount_rate: Decimal, years_from_ref: Decimal) -> Decimal:
    return amount / ((Decimal("1") + discount_rate) ** years_from_ref)

def compute_earnings_table(
    start_date: datetime,
    end_date: datetime,
    wage_base: float,
    residual_base: float,
    growth_rate: float,
    discount_rate: float,
    adjustment_factor: float,
    date_of_birth: Optional[datetime] = None,
    reference_start: Optional[datetime] = None
) -> Tuple[pd.DataFrame, Decimal, Decimal]:

    if end_date < start_date:
        logging.error("End date cannot be earlier than start date.")
        return pd.DataFrame(), Decimal("0"), Decimal("0")

    if reference_start is None:
        reference_start = start_date

    wb = Decimal(str(wage_base))
    rb = Decimal(str(residual_base))
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

    current_year = start_date.year
    segment_start = start_date
    final_wb = wb
    final_rb = rb

    while True:
        year_start = datetime(year=current_year, month=1, day=1)
        if year_start < segment_start:
            year_start = segment_start

        year_end = datetime(year=current_year, month=12, day=31)
        if year_end > end_date:
            year_end = end_date

        if year_start > year_end:
            break

        days_in_segment = (year_end - year_start).days + 1
        if days_in_segment < 1:
            break

        portion = Decimal(str(days_in_segment)) / Decimal("365.25")

        if date_of_birth:
            age_this_year = relativedelta(year_start, date_of_birth).years
        else:
            age_this_year = ""

        net_base = wb - rb
        if net_base < Decimal("0"):
            net_base = Decimal("0")

        gross_earnings = net_base * portion
        adjusted_earnings = gross_earnings * adj_dec

        yrs_from_ref = Decimal(str((year_start - reference_start).days)) / Decimal("365.25")
        present_value = compute_present_value(adjusted_earnings, d_dec, yrs_from_ref)

        records["Year"].append(str(current_year))
        records["Age"].append(str(age_this_year))
        records["PortionOfYear"].append(f"{portion:.4f}")
        records["WageBase"].append(format_currency(net_base.quantize(Decimal("0.01"))))
        records["GrossEarnings"].append(format_currency(gross_earnings.quantize(Decimal("0.01"))))
        records["AdjustedEarnings"].append(format_currency(adjusted_earnings.quantize(Decimal("0.01"))))
        records["PresentValue"].append(format_currency(present_value.quantize(Decimal("0.01"))))

        wb *= (Decimal("1") + g_dec)
        rb *= (Decimal("1") + g_dec)

        if year_end == end_date:
            final_wb = wb
            final_rb = rb
            break

        current_year += 1
        segment_start = year_end + relativedelta(days=1)

    df = pd.DataFrame(records)
    return df, final_wb, final_rb

@app.route("/earnings/<evaluee_id>", methods=["GET"])
def earnings_form(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))

    evaluee = EVALUEES[evaluee_id]
    return render_template_string(EARNINGS_FORM_TEMPLATE,
                                  evaluee_id=evaluee_id,
                                  evaluee=evaluee,
                                  default_wle=40.0,
                                  default_swb=46748.0,
                                  default_rec=0.0,
                                  default_aef=88.54)

@app.route("/earnings_submit/<evaluee_id>", methods=["POST"])
def earnings_submit(evaluee_id):
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))
    evaluee = EVALUEES[evaluee_id]

    form = request.form
    from time import time

    date_of_birth_str = form.get("date_of_birth", "").strip()
    date_of_injury_str = form.get("date_of_injury", "").strip()
    date_of_report_str = form.get("date_of_report", "").strip()

    wle = float(form.get("worklife_years", 40.0))
    swb = float(form.get("starting_wage_base", 46748.0))
    rec = float(form.get("residual_earning_capacity", 0.0))
    aef = float(form.get("adjusted_earnings_factor", 88.54))

    dor_dt = parse_mdy(date_of_report_str)
    if not dor_dt:
        flash("Invalid Date of Report. Must be MM/DD/YYYY.")
        return redirect(url_for("earnings_form", evaluee_id=evaluee_id))

    # Possibly override with evaluee's Demographics
    dob_dt = parse_mdy(date_of_birth_str) or evaluee.get("dob", None)
    doi_dt = parse_mdy(date_of_injury_str) or evaluee.get("doi", None)

    # If we have evaluee's retirement_date from Demographics, use that
    if "retirement_date" in evaluee:
        final_retirement_dt = evaluee["retirement_date"]
    else:
        # fallback
        final_retirement_dt = add_decimal_years(dor_dt, Decimal(str(wle)))

    # Pre-injury only if we have a valid doi_dt < dor_dt
    # We'll do multi-scenarios for discount vs growth
    # If discounting is OFF, we force discount rates to [0.0]
    disc_rates = evaluee["discount_rates"] if evaluee["uses_discounting"] else [0.0]

    scenario_key = f"{evaluee_id}_{time()}"
    scenario_data = {
        "date_of_birth": dob_dt,
        "date_of_injury": doi_dt,
        "date_of_report": dor_dt,
        "retirement_dt": final_retirement_dt,
        "swb": swb,
        "rec": rec,
        "aef": aef,
        "discount_rates": disc_rates,
        "growth_rates": [2.0, 3.5, 5.0],  # you can also store in evaluee or ask user
    }

    EVALUEES[scenario_key] = scenario_data

    return redirect(url_for("earnings_results", evaluee_id=evaluee_id, key=scenario_key))

@app.route("/earnings_results/<evaluee_id>/<key>", methods=["GET"])
def earnings_results(evaluee_id, key):
    if key not in EVALUEES:
        flash("No scenario found with that key.")
        return redirect(url_for("earnings_form", evaluee_id=evaluee_id))
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))

    evaluee = EVALUEES[evaluee_id]
    scenario_data = EVALUEES[key]

    final_ret_dt = scenario_data["retirement_dt"]
    final_ret_date_str = final_ret_dt.strftime("%m/%d/%Y")

    disc_rates = scenario_data["discount_rates"]
    growths = scenario_data["growth_rates"]

    scenarios = []
    i = 0

    for d_rate in disc_rates:
        for g_rate in growths:
            i += 1

            # pre-injury
            pre_pv = Decimal("0")
            pre_df = pd.DataFrame()
            fw_pre = Decimal(str(scenario_data["swb"]))
            fr_pre = Decimal(str(scenario_data["rec"]))

            if scenario_data["date_of_injury"] and scenario_data["date_of_injury"] < scenario_data["date_of_report"]:
                pre_df, fw_pre, fr_pre = compute_earnings_table(
                    start_date=scenario_data["date_of_injury"],
                    end_date=scenario_data["date_of_report"],
                    wage_base=float(fw_pre),
                    residual_base=float(fr_pre),
                    growth_rate=g_rate,
                    discount_rate=d_rate,
                    adjustment_factor=scenario_data["aef"],
                    date_of_birth=scenario_data["date_of_birth"],
                    reference_start=scenario_data["date_of_injury"]
                )
                pre_pv = sum_currency_column(pre_df["PresentValue"])

            # post-injury
            post_df, fw_post, fr_post = compute_earnings_table(
                start_date=scenario_data["date_of_report"],
                end_date=final_ret_dt,
                wage_base=float(fw_pre),
                residual_base=float(fr_pre),
                growth_rate=g_rate,
                discount_rate=d_rate,
                adjustment_factor=scenario_data["aef"],
                date_of_birth=scenario_data["date_of_birth"],
                reference_start=scenario_data["date_of_report"]
            )
            post_pv = sum_currency_column(post_df["PresentValue"])

            scenarios.append({
                "discount_rate": d_rate,
                "growth_rate": g_rate,
                "pre_pv": format_currency(pre_pv),
                "post_pv": format_currency(post_pv),
                "pre_df": pre_df,
                "post_df": post_df
            })

    return render_template_string(
        EARNINGS_RESULTS_TEMPLATE,
        evaluee=evaluee,
        evaluee_id=evaluee_id,
        eval_key=key,
        final_ret_date_str=final_ret_date_str,
        scenarios=scenarios
    )

@app.route("/download_excel/<evaluee_id>/<key>", methods=["GET"])
def download_excel(evaluee_id, key):
    if key not in EVALUEES:
        flash("No scenario found with that key.")
        return redirect(url_for("earnings_form", evaluee_id=evaluee_id))
    if evaluee_id not in EVALUEES:
        flash("Invalid Evaluee ID.")
        return redirect(url_for("start"))

    scenario_data = EVALUEES[key]
    evaluee = EVALUEES[evaluee_id]

    disc_rates = scenario_data["discount_rates"]
    growths = scenario_data["growth_rates"]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        s_idx = 1
        for d_rate in disc_rates:
            for g_rate in growths:
                # pre
                fw_pre = Decimal(str(scenario_data["swb"]))
                fr_pre = Decimal(str(scenario_data["rec"]))
                pre_df = pd.DataFrame()
                if scenario_data["date_of_injury"] and scenario_data["date_of_injury"] < scenario_data["date_of_report"]:
                    pre_df, fw_pre, fr_pre = compute_earnings_table(
                        start_date=scenario_data["date_of_injury"],
                        end_date=scenario_data["date_of_report"],
                        wage_base=float(fw_pre),
                        residual_base=float(fr_pre),
                        growth_rate=g_rate,
                        discount_rate=d_rate,
                        adjustment_factor=scenario_data["aef"],
                        date_of_birth=scenario_data["date_of_birth"],
                        reference_start=scenario_data["date_of_injury"]
                    )

                # post
                post_df, fw_post, fr_post = compute_earnings_table(
                    start_date=scenario_data["date_of_report"],
                    end_date=scenario_data["retirement_dt"],
                    wage_base=float(fw_pre),
                    residual_base=float(fr_pre),
                    growth_rate=g_rate,
                    discount_rate=d_rate,
                    adjustment_factor=scenario_data["aef"],
                    date_of_birth=scenario_data["date_of_birth"],
                    reference_start=scenario_data["date_of_report"]
                )

                sheet_name_pre = f"S{s_idx}_Pre_{d_rate}_{g_rate}"
                sheet_name_post = f"S{s_idx}_Post_{d_rate}_{g_rate}"
                pre_df.to_excel(writer, index=False, sheet_name=sheet_name_pre[:31])
                post_df.to_excel(writer, index=False, sheet_name=sheet_name_post[:31])
                s_idx += 1

    output.seek(0)
    fname = f"Earnings_{evaluee['first_name']}_{evaluee['last_name']}.xlsx"
    return send_file(output,
                     as_attachment=True,
                     download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------------------------------------------------
#                          RUN THE APP
# ---------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
