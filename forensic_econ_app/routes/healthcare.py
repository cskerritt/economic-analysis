from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from forensic_econ_app.models.models import db, Evaluee, HealthcareScenario, MedicalItem, CPIRate
from decimal import Decimal
from datetime import datetime
import decimal
import pandas as pd
import os
from tempfile import NamedTemporaryFile
from flask_login import login_required, current_user
from ..utils.life_care_plan import generate_life_care_plan_table
from openpyxl.utils import get_column_letter

healthcare = Blueprint('healthcare', __name__)

def compute_future_medical_costs(scenario):
    """Compute future medical costs based on scenario parameters."""
    print(f"DEBUG: Starting calculations for scenario {scenario.scenario_name}")
    
    # Determine scenario growth rate
    if scenario.growth_method == "CPI":
        scenario_growth_rate = CPIRate.get_rate("CPI") or Decimal('0.03')
    elif scenario.growth_method == "PCE":
        scenario_growth_rate = CPIRate.get_rate("PCE") or Decimal('0.025')
    elif scenario.growth_method == "Medical_CPI":
        scenario_growth_rate = CPIRate.get_rate("Medical_CPI") or Decimal('0.035')
    else:
        scenario_growth_rate = scenario.growth_rate_custom

    print(f"DEBUG: Growth rate: {scenario_growth_rate}")

    discount_rate = scenario.discount_rate
    partial_offset = scenario.partial_offset
    total_offset = scenario.total_offset
    projection_years = scenario.projection_years
    discounting_enabled = scenario.discount_method != 'none'

    print(f"DEBUG: Initial parameters - Discount rate: {discount_rate}, Projection years: {projection_years}")

    # If total_offset => discount_rate = growth_rate
    if total_offset:
        discount_rate = scenario_growth_rate

    # partial offset => net_discount in discrete time
    net_discount = discount_rate
    if partial_offset:
        net_discount = ((1 + discount_rate)/(1 + scenario_growth_rate)) - 1
        scenario_growth_rate = Decimal('0.0')  # treat growth as 0, discount = net_discount

    # if discount_method == 'net', treat user-supplied discount_rate as net
    if scenario.discount_method == 'net':
        net_discount = discount_rate

    print(f"DEBUG: Final discount rate: {net_discount}")

    # Create results dictionary with parameters
    results = {
        "parameters_used": {
            "growth_rate_effective": float(scenario_growth_rate),
            "discount_rate_effective": float(net_discount),
            "projection_years": projection_years,
            "partial_offset": partial_offset,
            "total_offset": total_offset,
            "discounting_enabled": discounting_enabled
        },
        "items_breakdown": [],
        "grand_total_present_value": 0.0,
        "grand_total_undiscounted": 0.0
    }

    # Convert medical items to the format expected by life care plan calculator
    items = []
    for item in scenario.medical_items:
        print(f"\nDEBUG: Processing item {item.label}")
        print(f"DEBUG: Raw annual cost: {item.annual_cost}")
        print(f"DEBUG: Raw growth rate: {item.growth_rate}")
        print(f"DEBUG: Is one time: {item.is_one_time}")
        print(f"DEBUG: Start year: {item.start_year}")
        print(f"DEBUG: Duration years: {item.duration_years}")
        
        # Ensure all numeric values are properly converted to float
        try:
            annual_cost = float(item.annual_cost) if item.annual_cost is not None else 0.0
            growth_rate = float(item.growth_rate) if item.growth_rate is not None else float(scenario_growth_rate)
            start_year = int(item.start_year) if item.start_year is not None else 1
            
            print(f"DEBUG: Converted annual cost: {annual_cost}")
            print(f"DEBUG: Converted growth rate: {growth_rate}")
            print(f"DEBUG: Converted start year: {start_year}")
            
            item_dict = {
                "name": item.label,
                "base_cost": annual_cost,
                "growth_rate": growth_rate,
                "pattern": "once" if item.is_one_time else "recurring",
                "year_offset": start_year - 1
            }
            
            if item.duration_years:
                item_dict["repeat_interval"] = 1.0
                item_dict["pattern"] = "interval"
            
            print(f"DEBUG: Final item dict: {item_dict}")
            items.append(item_dict)
        except (ValueError, TypeError) as e:
            print(f"DEBUG: Error processing item {item.label}: {str(e)}")
            continue

    # Calculate start age
    start_age = None
    if scenario.evaluee.date_of_birth:
        start_date = datetime.now()
        start_age = float(
            (start_date.year - scenario.evaluee.date_of_birth.year) +
            ((start_date.month - scenario.evaluee.date_of_birth.month) / 12.0) +
            ((start_date.day - scenario.evaluee.date_of_birth.day) / 365.25)
        )
    
    print(f"DEBUG: Start age: {start_age}")

    # Generate the life care plan table
    df = generate_life_care_plan_table(
        category_name=scenario.scenario_name,
        start_year=datetime.now().year,
        start_age=start_age or 0.0,
        duration_years=float(projection_years),
        items=items,
        annual_discount_rate=float(net_discount),
        discounting_enabled=discounting_enabled,
        frequency="annual"
    )

    print("\nDEBUG: Generated DataFrame head:")
    print(df.head())
    print("\nDEBUG: Generated DataFrame tail:")
    print(df.tail())

    # Process each item's breakdown
    for item in items:
        item_name = item["name"]
        yearly_details = []
        
        print(f"\nDEBUG: Processing results for item {item_name}")
        
        # Get the rows before the summary rows
        data_rows = df[df['Age'] != f"{item_name} TOTAL"].copy()
        data_rows = data_rows[pd.to_numeric(data_rows['Age'], errors='coerce').notna()]
        
        for _, row in data_rows.iterrows():
            if isinstance(row['Age'], str):
                continue
            
            try:
                year_detail = {
                    "year": int(row['Calendar Year']),
                    "projected_cost": float(row[f"{item_name} (Undiscounted)"]),
                    "present_value": float(row[f"{item_name} (Discounted)"]) if discounting_enabled else float(row[f"{item_name} (Undiscounted)"])
                }
                print(f"DEBUG: Year detail: {year_detail}")
                yearly_details.append(year_detail)
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error processing row for {item_name}: {str(e)}")
                continue
        
        try:
            # Get the item's total from the summary row
            total_row = df[df['Age'] == f"{item_name} TOTAL"].iloc[0]
            undiscounted_total = float(total_row[f"{item_name} (Undiscounted)"].replace(",", ""))
            discounted_total = float(total_row[f"{item_name} (Discounted)"].replace(",", "")) if discounting_enabled else undiscounted_total
            print(f"DEBUG: Item total - Undiscounted: {undiscounted_total}, Discounted: {discounted_total}")
            
            results["items_breakdown"].append({
                "label": item_name,
                "yearly_details": yearly_details,
                "item_present_value_sum": discounted_total,
                "item_undiscounted_sum": undiscounted_total
            })
        except (ValueError, TypeError, IndexError) as e:
            print(f"DEBUG: Error processing total for {item_name}: {str(e)}")
            continue

    # Get the grand total from the final row
    try:
        grand_total_row = df[df['Age'] == "Grand TOTAL"].iloc[0]
        results["grand_total_undiscounted"] = float(grand_total_row["Total (Undiscounted)"].replace(",", ""))
        results["grand_total_present_value"] = float(grand_total_row["Total (Discounted)"].replace(",", "")) if discounting_enabled else results["grand_total_undiscounted"]
        print(f"\nDEBUG: Grand totals - Undiscounted: {results['grand_total_undiscounted']}, Discounted: {results['grand_total_present_value']}")
    except (ValueError, TypeError, IndexError) as e:
        print(f"DEBUG: Error processing grand total: {str(e)}")

    results["notes"] = (
        "Computed using Eric Christensen's 2022 methodology for life care plan calculations. "
        "Partial/Total offset done in discrete-time form. All currency nominal. "
        "Individual growth rates and age ranges applied where specified."
    )
    
    return results

@healthcare.route('/healthcare/<int:evaluee_id>')
def healthcare_form(evaluee_id):
    """Display healthcare form for an evaluee."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenarios = HealthcareScenario.query.filter_by(evaluee_id=evaluee_id).all()
    cpi_rates = {
        'CPI': CPIRate.get_rate("CPI") or 3.0,
        'PCE': CPIRate.get_rate("PCE") or 2.5,
        'Medical_CPI': CPIRate.get_rate("Medical_CPI") or 3.5
    }
    return render_template('healthcare/form.html', 
                         evaluee=evaluee, 
                         scenarios=scenarios,
                         cpi_rates=cpi_rates,
                         now=datetime.now())

@healthcare.route('/healthcare/<int:evaluee_id>', methods=['POST'])
def create_scenario(evaluee_id):
    """Create a new healthcare scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    
    # Convert percentage inputs to decimal
    growth_rate_custom = Decimal(request.form.get('growth_rate_custom', '3.0')) / 100
    discount_rate = Decimal(request.form.get('discount_rate', '5.0')) / 100
    
    scenario = HealthcareScenario(
        evaluee_id=evaluee_id,
        scenario_name=request.form.get('scenario_name'),
        growth_method=request.form.get('growth_method', 'CPI'),
        growth_rate_custom=growth_rate_custom,
        discount_method=request.form.get('discount_method', 'nominal'),
        discount_rate=discount_rate,
        partial_offset=bool(request.form.get('partial_offset')),
        total_offset=bool(request.form.get('total_offset')),
        projection_years=int(request.form.get('projection_years', 20))
    )
    
    db.session.add(scenario)
    db.session.commit()
    
    flash('Healthcare scenario created successfully.', 'success')
    return redirect(url_for('healthcare.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario.id))

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>')
def view_scenario(evaluee_id, scenario_id):
    """View a healthcare scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    results = compute_future_medical_costs(scenario)
    return render_template('healthcare/view_scenario.html', 
                         evaluee=evaluee, 
                         scenario=scenario, 
                         results=results,
                         now=datetime.now())

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/edit', methods=['GET', 'POST'])
def edit_scenario(evaluee_id, scenario_id):
    """Edit a healthcare scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    if request.method == 'POST':
        scenario.scenario_name = request.form.get('scenario_name')
        scenario.growth_method = request.form.get('growth_method')
        scenario.growth_rate_custom = Decimal(request.form.get('growth_rate_custom', '3.0')) / 100
        scenario.discount_method = request.form.get('discount_method')
        scenario.discount_rate = Decimal(request.form.get('discount_rate', '5.0')) / 100
        scenario.partial_offset = bool(request.form.get('partial_offset'))
        scenario.total_offset = bool(request.form.get('total_offset'))
        
        # Use life expectancy as default if no projection years provided
        projection_years = request.form.get('projection_years')
        if not projection_years and evaluee.life_expectancy:
            scenario.projection_years = int(evaluee.life_expectancy)
        else:
            scenario.projection_years = int(projection_years or 20)
        
        db.session.commit()
        flash('Healthcare scenario updated successfully.', 'success')
        return redirect(url_for('healthcare.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    cpi_rates = {
        'CPI': CPIRate.get_rate("CPI") or 3.0,
        'PCE': CPIRate.get_rate("PCE") or 2.5,
        'Medical_CPI': CPIRate.get_rate("Medical_CPI") or 3.5
    }
    
    return render_template('healthcare/edit_scenario.html', 
                         evaluee=evaluee, 
                         scenario=scenario,
                         cpi_rates=cpi_rates,
                         now=datetime.now())

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/items', methods=['GET'])
def manage_items(evaluee_id, scenario_id):
    """Manage medical items for a scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    return render_template('healthcare/items.html', evaluee=evaluee, scenario=scenario)

@healthcare.route('/evaluee/<int:evaluee_id>/healthcare/<int:scenario_id>/items/add', methods=['POST'])
@login_required
def add_item(evaluee_id, scenario_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    # Verify ownership
    if evaluee.user_id != current_user.id:
        abort(403)
    if scenario.evaluee_id != evaluee_id:
        abort(400)
    
    # Get form data
    label = request.form.get('label')
    annual_cost = request.form.get('annual_cost', type=float)
    is_one_time = request.form.get('is_one_time') == 'on'
    
    # Get growth rate (convert from percentage to decimal)
    growth_rate_str = request.form.get('growth_rate')
    growth_rate = float(growth_rate_str) / 100 if growth_rate_str else None
    
    # Get age ranges (now as floats)
    age_initiated = request.form.get('age_initiated', type=float)
    age_through = request.form.get('age_through', type=float)
    
    # Get year-based timing (now optional)
    start_year = request.form.get('start_year', type=int)
    duration_years = request.form.get('duration_years', type=int)
    
    # Validate inputs
    if not label or annual_cost is None or annual_cost < 0:
        flash('Please provide a valid label and cost.', 'danger')
        return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    if growth_rate is not None and (growth_rate < 0 or growth_rate > 1):
        flash('Growth rate must be between 0% and 100%.', 'danger')
        return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    if age_initiated is not None and age_through is not None and age_initiated > age_through:
        flash('Age initiated must be less than or equal to age through.', 'danger')
        return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    if start_year is not None and start_year < 1:
        flash('Start year must be 1 or greater.', 'danger')
        return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    if duration_years is not None and duration_years < 1:
        flash('Duration must be 1 year or greater.', 'danger')
        return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    # Create new medical item
    item = MedicalItem(
        label=label,
        annual_cost=annual_cost,
        is_one_time=is_one_time,
        growth_rate=growth_rate,
        age_initiated=age_initiated,
        age_through=age_through,
        start_year=start_year or 1,  # Default to 1 if not specified
        duration_years=duration_years,
        scenario_id=scenario_id
    )
    
    db.session.add(item)
    db.session.commit()
    
    flash(f'Added medical cost: {label}', 'success')
    return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/items/<int:item_id>/delete', methods=['POST'])
def delete_item(evaluee_id, scenario_id, item_id):
    """Delete a medical item."""
    item = MedicalItem.query.get_or_404(item_id)
    if item.scenario_id != scenario_id:
        flash('Invalid item for this scenario.', 'error')
        return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    db.session.delete(item)
    db.session.commit()
    flash('Medical item deleted successfully.', 'success')
    return redirect(url_for('healthcare.manage_items', evaluee_id=evaluee_id, scenario_id=scenario_id))

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/duplicate', methods=['POST'])
def duplicate_scenario(evaluee_id, scenario_id):
    """Duplicate a healthcare scenario."""
    original = HealthcareScenario.query.get_or_404(scenario_id)
    if original.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    new_scenario = HealthcareScenario(
        evaluee_id=evaluee_id,
        scenario_name=f"{original.scenario_name} (Copy)",
        growth_method=original.growth_method,
        growth_rate_custom=original.growth_rate_custom,
        discount_method=original.discount_method,
        discount_rate=original.discount_rate,
        partial_offset=original.partial_offset,
        total_offset=original.total_offset,
        projection_years=original.projection_years
    )
    db.session.add(new_scenario)
    db.session.flush()  # Get the new scenario ID
    
    # Copy medical items
    for item in original.medical_items:
        new_item = MedicalItem(
            scenario_id=new_scenario.id,
            label=item.label,
            annual_cost=item.annual_cost
        )
        db.session.add(new_item)
    
    db.session.commit()
    flash('Healthcare scenario duplicated successfully.', 'success')
    return redirect(url_for('healthcare.view_scenario', evaluee_id=evaluee_id, scenario_id=new_scenario.id))

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/delete', methods=['POST'])
def delete_scenario(evaluee_id, scenario_id):
    """Delete a healthcare scenario."""
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    try:
        db.session.delete(scenario)
        db.session.commit()
        flash('Healthcare scenario deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting healthcare scenario.', 'error')
    
    return redirect(url_for('evaluee.view', evaluee_id=evaluee_id))

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/export')
def export_scenario(evaluee_id, scenario_id):
    """Export healthcare scenario to Excel."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    results = compute_future_medical_costs(scenario)
    current_year = datetime.now().year
    
    # Generate the life care plan table
    # Calculate start age
    start_age = None
    if evaluee.date_of_birth:
        start_date = datetime.now()
        start_age = float(
            (start_date.year - evaluee.date_of_birth.year) +
            ((start_date.month - evaluee.date_of_birth.month) / 12.0) +
            ((start_date.day - evaluee.date_of_birth.day) / 365.25)
        )
    
    # Convert medical items to the format expected by life care plan calculator
    items = []
    for item in scenario.medical_items:
        try:
            annual_cost = float(item.annual_cost) if item.annual_cost is not None else 0.0
            growth_rate = float(item.growth_rate) if item.growth_rate is not None else float(results['parameters_used']['growth_rate_effective'])
            start_year = int(item.start_year) if item.start_year is not None else 1
            
            item_dict = {
                "name": item.label,
                "base_cost": annual_cost,
                "growth_rate": growth_rate,
                "pattern": "once" if item.is_one_time else "recurring",
                "year_offset": start_year - 1
            }
            
            if item.duration_years:
                item_dict["repeat_interval"] = 1.0
                item_dict["pattern"] = "interval"
            
            items.append(item_dict)
        except (ValueError, TypeError) as e:
            continue
    
    # Generate the life care plan table
    df = generate_life_care_plan_table(
        category_name=scenario.scenario_name,
        start_year=datetime.now().year,
        start_age=start_age or 0.0,
        duration_years=float(scenario.projection_years),
        items=items,
        annual_discount_rate=float(results['parameters_used']['discount_rate_effective']),
        discounting_enabled=True,
        frequency="annual"
    )
    
    # Create a temporary file
    with NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        writer = pd.ExcelWriter(tmp.name, engine='openpyxl')
        
        # Parameters sheet
        params_data = {
            'Parameter': [
                'Scenario Name',
                'Growth Method',
                'Custom Growth Rate' if scenario.growth_method == 'custom' else 'Effective Growth Rate',
                'Discount Method',
                'Discount Rate',
                'Projection Years',
                'Partial Offset',
                'Total Offset'
            ],
            'Value': [
                scenario.scenario_name,
                scenario.growth_method,
                f"{float(scenario.growth_rate_custom * 100 if scenario.growth_method == 'custom' else results['parameters_used']['growth_rate_effective']):.2f}%",
                scenario.discount_method,
                f"{float(scenario.discount_rate * 100):.2f}%",
                scenario.projection_years,
                'Yes' if scenario.partial_offset else 'No',
                'Yes' if scenario.total_offset else 'No'
            ]
        }
        pd.DataFrame(params_data).to_excel(writer, sheet_name='Parameters', index=False)
        
        # Create yearly breakdown data in the example format
        yearly_data = []
        
        # Add header rows with initial parameters
        header_data = {
            'Year': '',
            'Age': '2025 Cost:',
        }
        duration_data = {
            'Year': '',
            'Age': 'Duration (Years)',
        }
        growth_data = {
            'Year': '',
            'Age': 'Growth Rate:',
        }
        discount_data = {
            'Year': '',
            'Age': 'Discount Rate:',
        }
        
        # Add columns for each medical item and total
        for item in scenario.medical_items:
            header_data[item.label] = f"${float(item.annual_cost):,.2f}"
            duration_data[item.label] = f"{item.duration_years or 1.00:.2f}"
            growth_data[item.label] = f"{float(item.growth_rate * 100 if item.growth_rate is not None else results['parameters_used']['growth_rate_effective']):.2f}%"
        
        # Add discount rate row
        discount_rate_str = f"{float(results['parameters_used']['discount_rate_effective'] * 100):.2f}%"
        for item in scenario.medical_items:
            discount_data[item.label] = discount_rate_str
        
        yearly_data.append(header_data)
        yearly_data.append(duration_data)
        yearly_data.append(growth_data)
        yearly_data.append(discount_data)
        
        # Get the data rows before any summary rows
        data_rows = df[df['Age'].apply(lambda x: not isinstance(x, str) or x.replace('.', '').isdigit())].copy()
        
        # Add year-by-year breakdown
        for _, row in data_rows.iterrows():
            year_data = {
                'Year': int(row['Calendar Year']),
                'Age': f"{float(row['Age']):.2f}"
            }
            
            total_cost = 0
            total_pv = 0
            # Add data for each medical item
            for item in scenario.medical_items:
                cost = float(row[f"{item.label} (Undiscounted)"])
                pv = float(row[f"{item.label} (Discounted)"])
                year_data[item.label] = f"${cost:,.2f}"
                total_cost += cost
                total_pv += pv
            
            year_data['Total Cost'] = f"${total_cost:,.2f}"
            year_data['Present Value'] = f"${total_pv:,.2f}"
            yearly_data.append(year_data)
        
        # Add final total row
        total_row = {
            'Year': '',
            'Age': 'Total:',
        }
        
        # Add item totals
        for item in scenario.medical_items:
            item_total = float(df[df['Age'] == f"{item.label} TOTAL"].iloc[0][f"{item.label} (Undiscounted)"].replace(',', ''))
            total_row[item.label] = f"${item_total:,.2f}"
        
        # Add grand totals
        grand_total_row = df[df['Age'] == "Grand TOTAL"].iloc[0]
        total_row['Total Cost'] = f"${float(grand_total_row['Total (Undiscounted)'].replace(',', '')):,.2f}"
        total_row['Present Value'] = f"${float(grand_total_row['Total (Discounted)'].replace(',', '')):,.2f}"
        yearly_data.append(total_row)
        
        # Create DataFrame and write to Excel
        yearly_df = pd.DataFrame(yearly_data)
        yearly_df.to_excel(writer, sheet_name=scenario.scenario_name, index=False)
        
        # Format the worksheet
        worksheet = writer.sheets[scenario.scenario_name]
        
        # Set column widths
        for col_idx, col_name in enumerate(yearly_df.columns):
            col_letter = get_column_letter(col_idx + 1)
            worksheet.column_dimensions[col_letter].width = 15
        
        # Add borders and formatting
        from openpyxl.styles import Border, Side, Alignment, Font
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Apply borders and center alignment to all cells
        for row in worksheet.iter_rows(min_row=1, max_row=worksheet.max_row):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
        
        # Make headers bold
        for row in range(1, 5):  # Now including discount rate row
            for cell in worksheet[row]:
                cell.font = Font(bold=True)
        
        writer.close()
        
        return send_file(
            tmp.name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'healthcare_scenario_{scenario.scenario_name}_{evaluee.last_name}.xlsx'
        ) 