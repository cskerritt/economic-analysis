from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io, json, logging

from config import Config
from models import db, Evaluee
from calculators import (
    calculate_worklife_factor_logic,
    calculate_aef_logic,
    compute_earnings_table
)
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import pandas as pd

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_object(Config)

db.init_app(app)

# Log to a file for auditing
logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

# -----------------------------------------
#    DATABASE SETUP COMMAND (one-time)
# -----------------------------------------
@app.before_first_request
def create_tables():
    db.create_all()

# -----------------------------------------
#    HOME PAGE
# -----------------------------------------
@app.route("/")
def index():
    evaluees = Evaluee.query.all()
    return render_template("index.html", evaluees=evaluees)

@app.route("/new_evaluee", methods=["POST"])
def new_evaluee():
    """Creates a new Evaluee and stores in the DB."""
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    state = request.form.get("state", "").strip()
    discounting = request.form.get("discounting", "") == "yes"
    discount_rates_str = request.form.get("discount_rates", "3,5,7")

    if not first_name or not last_name or not state:
        flash("Missing required fields.")
        return redirect(url_for("index"))

    if not discounting:
        # Force discount rates to "0"
        discount_rates_str = "0"

    new_eval = Evaluee(
        first_name=first_name,
        last_name=last_name,
        state=state,
        uses_discounting=discounting,
        discount_rates_str=discount_rates_str
    )
    db.session.add(new_eval)
    db.session.commit()
    logging.info(f"Created new Evaluee: {first_name} {last_name}, discount={discounting}")
    flash("Evaluee created successfully.")
    return redirect(url_for("index"))

@app.route("/home/<int:eid>")
def evaluee_home(eid):
    eval_obj = Evaluee.query.get_or_404(eid)
    return render_template("evaluee_home.html", evaluee=eval_obj)

# -----------------------------------------
#  IMPORT/EXPORT Evaluees in JSON
# -----------------------------------------
@app.route("/export_evaluees", methods=["GET"])
def export_evaluees():
    """Exports all Evaluees as JSON."""
    all_evals = Evaluee.query.all()
    data = [x.to_dict() for x in all_evals]
    return jsonify(data)

@app.route("/import_evaluees", methods=["POST"])
def import_evaluees():
    """Imports Evaluees from a JSON payload."""
    try:
        payload = request.json  # assume array of evaluees
        if not isinstance(payload, list):
            raise ValueError("Expected a list of evaluees.")
        imported_count = 0
        for item in payload:
            # Minimal check
            new_eval = Evaluee(
                first_name=item.get("first_name", "Unknown"),
                last_name=item.get("last_name", "Unknown"),
                state=item.get("state", "Unknown"),
                uses_discounting=item.get("uses_discounting", True),
                discount_rates_str=item.get("discount_rates_str", "3,5,7")
            )
            db.session.add(new_eval)
            imported_count += 1
        db.session.commit()
        return jsonify({"message": f"Imported {imported_count} evaluees."}), 200
    except Exception as e:
        logging.error(f"Error importing evaluees: {e}")
        return jsonify({"error": str(e)}), 400

# -----------------------------------------
#  1) WORKLIFE FACTOR
# -----------------------------------------
@app.route("/worklife/<int:eid>", methods=["GET", "POST"])
def worklife(eid):
    evaluee = Evaluee.query.get_or_404(eid)
    if request.method == "POST":
        wle = float(request.form.get("wle", 0))
        yfs = float(request.form.get("yfs", 0))
        result = calculate_worklife_factor_logic(wle, yfs)
        logging.info(f"Worklife calculation for Evaluee {eid}: wle={wle}, yfs={yfs}, result={result}")
        return render_template("worklife_result.html", evaluee=evaluee, factor=result)
    return render_template("worklife_form.html", evaluee=evaluee)

# -----------------------------------------
#  2) AEF CALCULATOR
# -----------------------------------------
@app.route("/aef/<int:eid>", methods=["GET", "POST"])
def aef(eid):
    evaluee = Evaluee.query.get_or_404(eid)
    if request.method == "POST":
        try:
            gross_base = float(request.form["gross_base"])
            wla = float(request.form["wla"])
            uf = float(request.form["uf"])
            fb = float(request.form["fb"])
            tl = float(request.form["tl"])
            wd = ("wrongful_death" in request.form)
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
            logging.info(f"AEF calc for Evaluee {eid} => final AEF: {final_aef}")
            return render_template("aef_result.html", evaluee=evaluee, df=df, final_aef=final_aef)
        except ValueError as e:
            flash(f"Invalid input: {e}")
            return redirect(url_for("aef", eid=eid))
    return render_template("aef_form.html", evaluee=evaluee)

# -----------------------------------------
#  3) DEMOGRAPHICS (simplified example)
# -----------------------------------------
@app.route("/demographics/<int:eid>", methods=["GET", "POST"])
def demographics(eid):
    evaluee = Evaluee.query.get_or_404(eid)
    if request.method == "POST":
        # Example: store DOB, DOI, compute retirement_date
        dob_str = request.form.get("dob", "")
        doi_str = request.form.get("doi", "")
        evaluee.dob = dob_str
        evaluee.doi = doi_str
        # Suppose we do not do the full logic here for brevity
        db.session.commit()
        flash("Demographics saved.")
        return redirect(url_for("evaluee_home", eid=eid))
    return render_template("demographics.html", evaluee=evaluee)

# -----------------------------------------
#  4) EARNINGS CALCULATOR (MULTI-SCENARIO)
# -----------------------------------------
@app.route("/earnings/<int:eid>", methods=["GET", "POST"])
def earnings(eid):
    evaluee = Evaluee.query.get_or_404(eid)
    if request.method == "POST":
        date_of_report = request.form["date_of_report"].strip()
        wle = float(request.form.get("worklife_years", 40.0))
        # etc. We do partial usage for demonstration

        # Suppose we do partial scenario expansions
        # evaluee.get_discount_rates() gives discount rates
        # We'll use a fixed set of growth rates plus an extra scenario for personal consumption

        growth_rates = [2.0, 3.5, 5.0]
        consumption_scenarios = [0.0, 10.0]  # personal consumption variation

        results = []
        for d_rate in evaluee.get_discount_rates():
            for g_rate in growth_rates:
                for cons in consumption_scenarios:
                    # run a pseudo-calculation...
                    # (In reality, you'd compute a pre-injury & post-injury table, etc.)
                    result_tag = f"d={d_rate}, g={g_rate}, pc={cons}"
                    results.append(result_tag)

        # Just show them in a list
        flash("Ran multi-scenario earnings analysis.")
        return render_template("earnings_result.html", evaluee=evaluee, results=results)
    return render_template("earnings_form.html", evaluee=evaluee)

# -----------------------------------------
#   RUN
# -----------------------------------------
if __name__ == "__main__":
    app.run()
