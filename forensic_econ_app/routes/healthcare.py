from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from forensic_econ_app.models.models import db, Evaluee, HealthcareScenario, MedicalItem, CPIRate
from decimal import Decimal
from datetime import datetime
import decimal
import pandas as pd
import os
from tempfile import NamedTemporaryFile

healthcare = Blueprint('healthcare', __name__)

def compute_future_medical_costs(scenario):
    """Compute future medical costs based on scenario parameters."""
    # Determine growth rate
    if scenario.growth_method == "CPI":
        growth_rate = CPIRate.get_rate("CPI") or Decimal('0.03')
    elif scenario.growth_method == "PCE":
        growth_rate = CPIRate.get_rate("PCE") or Decimal('0.025')
    elif scenario.growth_method == "Medical_CPI":
        growth_rate = CPIRate.get_rate("Medical_CPI") or Decimal('0.035')
    else:
        growth_rate = scenario.growth_rate_custom

    discount_rate = scenario.discount_rate
    partial_offset = scenario.partial_offset
    total_offset = scenario.total_offset
    projection_years = scenario.projection_years

    # If total_offset => discount_rate = growth_rate
    if total_offset:
        discount_rate = growth_rate

    # partial offset => net_discount in discrete time
    net_discount = discount_rate
    if partial_offset:
        net_discount = ((1 + discount_rate)/(1 + growth_rate)) - 1
        growth_rate = Decimal('0.0')  # treat growth as 0, discount = net_discount

    # if discount_method == 'net', treat user-supplied discount_rate as net
    if scenario.discount_method == 'net':
        net_discount = discount_rate

    results = {
        "parameters_used": {
            "growth_rate_effective": float(growth_rate),
            "discount_rate_effective": float(net_discount),
            "projection_years": projection_years,
            "partial_offset": partial_offset,
            "total_offset": total_offset
        },
        "items_breakdown": [],
        "grand_total_present_value": 0.0
    }

    total_present_value = Decimal('0.0')
    
    for item in scenario.medical_items:
        yearly_details = []
        base_cost = item.annual_cost
        
        for yr in range(1, projection_years + 1):
            future_cost = base_cost * ((1 + growth_rate)**yr)
            discount_factor = (1 + net_discount)**yr
            pres_val = future_cost / discount_factor
            
            yearly_details.append({
                "year": yr,
                "projected_cost": float(round(future_cost, 2)),
                "present_value": float(round(pres_val, 2))
            })
        
        item_sum = sum(Decimal(str(x["present_value"])) for x in yearly_details)
        total_present_value += item_sum
        
        results["items_breakdown"].append({
            "label": item.label,
            "yearly_details": yearly_details,
            "item_present_value_sum": float(round(item_sum, 2))
        })
    
    results["grand_total_present_value"] = float(round(total_present_value, 2))
    results["notes"] = (
        "Computed using references in 'A Sampling of Methods to Calculate Losses' Chapter 12, "
        "Gaughan & Luporini (2020), Bowles & Lewis (2000). "
        "Partial/Total offset done in discrete-time form. All currency nominal."
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

@healthcare.route('/healthcare/<int:evaluee_id>/scenario/<int:scenario_id>/items/add', methods=['POST'])
def add_item(evaluee_id, scenario_id):
    """Add a new medical item to a scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = HealthcareScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('healthcare.healthcare_form', evaluee_id=evaluee_id))
    
    try:
        item = MedicalItem(
            scenario_id=scenario_id,
            label=request.form.get('label'),
            annual_cost=Decimal(request.form.get('annual_cost', '0'))
        )
        db.session.add(item)
        db.session.commit()
        flash('Medical item added successfully.', 'success')
    except (ValueError, decimal.InvalidOperation):
        flash('Invalid cost value provided.', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Error adding medical item.', 'error')
    
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
        
        # Create consolidated data for all items
        years = range(1, scenario.projection_years + 1)
        consolidated_data = {
            'Year': [current_year + yr - 1 for yr in years],
            'Age': [(current_year + yr - 1 - evaluee.date_of_birth.year + 
                    ((datetime.now().month, datetime.now().day) >= 
                     (evaluee.date_of_birth.month, evaluee.date_of_birth.day))) 
                   if evaluee.date_of_birth else 'N/A' 
                   for yr in years],
            'Portion': [(yr - (int(yr) - 1)) * 100 for yr in years]  # As percentage
        }
        
        # Add columns for each medical item's projected cost and present value
        total_projected = [0] * len(years)
        total_present = [0] * len(years)
        
        for item in results['items_breakdown']:
            item_label = item['label']
            projected_costs = []
            present_values = []
            
            for i, detail in enumerate(item['yearly_details']):
                portion = years[i] - (int(years[i]) - 1)
                projected = detail['projected_cost'] * portion
                present = detail['present_value'] * portion
                projected_costs.append(projected)
                present_values.append(present)
                total_projected[i] += projected
                total_present[i] += present
            
            consolidated_data[f"{item_label} - Projected"] = projected_costs
            consolidated_data[f"{item_label} - Present Value"] = present_values
        
        # Add total columns
        consolidated_data['Total Projected Cost'] = total_projected
        consolidated_data['Total Present Value'] = total_present
        
        # Create DataFrame and format it
        df = pd.DataFrame(consolidated_data)
        
        # Format numeric columns
        for col in df.columns:
            if col == 'Year':
                df[col] = df[col].astype(int)
            elif col == 'Age':
                continue  # Skip age formatting as it might contain 'N/A'
            elif col == 'Portion':
                df[col] = df[col].apply(lambda x: f"{x:.2f}%")
            else:
                df[col] = df[col].apply(lambda x: f"${x:,.2f}")
        
        # Write to Excel
        df.to_excel(writer, sheet_name='Detailed Breakdown', index=False)
        
        # Adjust column widths
        worksheet = writer.sheets['Detailed Breakdown']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
        
        # Add summary at the bottom
        summary_row = len(df) + 3  # Leave a blank row
        worksheet.cell(row=summary_row, column=1, value="Grand Total Present Value")
        worksheet.cell(row=summary_row, column=df.shape[1], 
                      value=f"${results['grand_total_present_value']:,.2f}")
        
        writer.close()
        
        # Send the file
        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=f'healthcare_scenario_{scenario.id}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ) 