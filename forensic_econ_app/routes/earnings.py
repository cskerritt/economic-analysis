from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from ..models.models import db, Evaluee, EarningsScenario, OffsetWage
from ..utils.calculations import compute_earnings_table, export_to_excel
from datetime import datetime
from decimal import Decimal
import os
from tempfile import mkstemp

bp = Blueprint('earnings', __name__)

@bp.route('/earnings/<int:evaluee_id>', methods=['GET', 'POST'])
def form(evaluee_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    
    if request.method == 'POST':
        # Get and validate inputs
        try:
            wage_base = float(request.form.get('wage_base'))
            residual_base = float(request.form.get('residual_base', 0))
            growth_rate = float(request.form.get('growth_rate', 0))
            adjustment_factor = float(request.form.get('adjustment_factor', 100))
            
            # Convert percentages if needed
            if growth_rate > 100:  # If entered as percentage (e.g. 550 for 5.5%)
                growth_rate = growth_rate / 100
            
            scenario = EarningsScenario(
                evaluee_id=evaluee_id,
                scenario_name=request.form.get('scenario_name'),
                start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d'),
                end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d'),
                wage_base=wage_base,
                residual_base=residual_base,
                growth_rate=growth_rate,
                adjustment_factor=adjustment_factor
            )
            
            db.session.add(scenario)
            db.session.commit()
            flash('Earnings scenario created successfully.')
            return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario.id))
        except (ValueError, TypeError) as e:
            db.session.rollback()
            flash(f'Error creating earnings scenario: Invalid input values')
            return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
        except Exception as e:
            db.session.rollback()
            flash('Error creating earnings scenario.')
            return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    return render_template('earnings/form.html', evaluee=evaluee, evaluee_id=evaluee_id)

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>/offset', methods=['POST'])
def add_offset_wage(evaluee_id, scenario_id):
    """Add an offset wage for a specific year."""
    scenario = EarningsScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        return jsonify({'error': 'Invalid scenario for this evaluee'}), 400
    
    try:
        year = int(request.form.get('year'))
        amount = float(request.form.get('amount'))
        description = request.form.get('description', '')
        
        # Validate year is within scenario range
        if year < scenario.start_date.year or year > scenario.end_date.year:
            flash('Offset year must be within the scenario date range.')
            return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario_id))
        
        # Check if offset wage already exists for this year
        existing_offset = OffsetWage.query.filter_by(scenario_id=scenario_id, year=year).first()
        if existing_offset:
            existing_offset.amount = amount
            existing_offset.description = description
            flash(f'Updated existing offset wage for year {year}.')
        else:
            offset_wage = OffsetWage(
                scenario_id=scenario_id,
                year=year,
                amount=amount,
                description=description
            )
            db.session.add(offset_wage)
            flash(f'Added new offset wage for year {year}.')
        
        db.session.commit()
        
        return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario_id))
    
    except (ValueError, TypeError) as e:
        flash(f'Error adding offset wage: {str(e)}')
        return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario_id))

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>/offset/<int:offset_id>', methods=['DELETE'])
def delete_offset_wage(evaluee_id, scenario_id, offset_id):
    """Delete an offset wage."""
    offset_wage = OffsetWage.query.get_or_404(offset_id)
    
    if offset_wage.scenario_id != scenario_id:
        return jsonify({'error': 'Invalid offset wage for this scenario'}), 400
    
    try:
        db.session.delete(offset_wage)
        db.session.commit()
        return jsonify({'message': 'Offset wage deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>')
def view_scenario(evaluee_id, scenario_id):
    """View earnings scenario with offset wages."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = EarningsScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    # Create dictionary of offset wages by year
    offset_wages = {ow.year: float(ow.amount) for ow in scenario.offset_wages}
    
    raw_table, display_table, total_pv, total_loss = compute_earnings_table(
        scenario.start_date,
        scenario.end_date,
        float(scenario.wage_base),
        float(scenario.residual_base),
        float(scenario.growth_rate),
        float(evaluee.discount_rates[0] / 100) if evaluee.uses_discounting else None,
        float(scenario.adjustment_factor),
        evaluee.date_of_birth,
        offset_wages=offset_wages
    )
    
    scenario.present_value = total_pv
    scenario.total_loss = total_loss
    db.session.commit()
    
    return render_template('earnings/view_scenario.html', 
                         evaluee=evaluee, 
                         scenario=scenario, 
                         earnings_table=display_table,
                         raw_earnings_table=raw_table,
                         evaluee_id=evaluee_id)

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>/delete', methods=['POST'])
def delete_scenario(evaluee_id, scenario_id):
    scenario = EarningsScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    try:
        db.session.delete(scenario)
        db.session.commit()
        flash('Earnings scenario deleted successfully.')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting earnings scenario.')
    
    return redirect(url_for('earnings.form', evaluee_id=evaluee_id))

@bp.route('/<int:evaluee_id>/export')
def export_scenario(evaluee_id):
    """Export earnings scenario to Excel."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario_id = request.args.get('scenario_id', type=int)
    
    if not scenario_id:
        flash('No scenario specified for export.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    scenario = EarningsScenario.query.get_or_404(scenario_id)
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    try:
        # Compute earnings table
        raw_table, _, _, _ = compute_earnings_table(
            scenario.start_date,
            scenario.end_date,
            float(scenario.wage_base),
            float(scenario.residual_base),
            float(scenario.growth_rate),
            float(evaluee.discount_rates[0] / 100) if evaluee.uses_discounting else None,
            float(scenario.adjustment_factor),
            evaluee.date_of_birth,
            include_discounting=evaluee.uses_discounting
        )
        
        # Create temporary file for Excel export
        temp_dir = os.path.dirname(os.path.abspath(__file__))
        temp_path = os.path.join(temp_dir, f'earnings_scenario_{scenario.id}.xlsx')
        
        # Export to Excel using raw values
        export_to_excel(raw_table, temp_path, include_discounting=evaluee.uses_discounting)
        
        return send_file(
            temp_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'earnings_scenario_{scenario.id}.xlsx'
        )
    
    except Exception as e:
        flash(f'Error exporting scenario: {str(e)}')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>/duplicate', methods=['POST'])
def duplicate_scenario(evaluee_id, scenario_id):
    """Duplicate an existing scenario with a new name."""
    original_scenario = EarningsScenario.query.get_or_404(scenario_id)
    
    if original_scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    try:
        # Create new scenario with same values
        new_name = request.form.get('new_name', f"{original_scenario.scenario_name} (Copy)")
        new_scenario = EarningsScenario(
            evaluee_id=evaluee_id,
            scenario_name=new_name,
            start_date=original_scenario.start_date,
            end_date=original_scenario.end_date,
            wage_base=original_scenario.wage_base,
            residual_base=original_scenario.residual_base,
            growth_rate=original_scenario.growth_rate,
            adjustment_factor=original_scenario.adjustment_factor
        )
        db.session.add(new_scenario)
        db.session.flush()  # Get new scenario ID
        
        # Duplicate offset wages
        for offset in original_scenario.offset_wages:
            new_offset = OffsetWage(
                scenario_id=new_scenario.id,
                year=offset.year,
                amount=offset.amount,
                description=offset.description
            )
            db.session.add(new_offset)
        
        db.session.commit()
        flash('Scenario duplicated successfully.')
        return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=new_scenario.id))
    
    except Exception as e:
        db.session.rollback()
        flash('Error duplicating scenario.')
        return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario_id))

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>/edit', methods=['GET', 'POST'])
def edit_scenario(evaluee_id, scenario_id):
    """Edit an existing earnings scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = EarningsScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    if request.method == 'POST':
        try:
            scenario.scenario_name = request.form.get('scenario_name')
            scenario.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
            scenario.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
            scenario.wage_base = float(request.form.get('wage_base'))
            
            # Handle residual base - allow zero or empty value
            residual_base = request.form.get('residual_base', '')
            scenario.residual_base = float(residual_base) if residual_base.strip() else 0
            
            # Handle growth rate - convert from percentage to decimal
            growth_rate = float(request.form.get('growth_rate', 0))
            scenario.growth_rate = growth_rate / 100  # Store as decimal (e.g., 2.25% -> 0.0225)
            
            scenario.adjustment_factor = float(request.form.get('adjustment_factor', 100))
            
            db.session.commit()
            flash('Scenario updated successfully.')
            return redirect(url_for('earnings.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario_id))
        except (ValueError, TypeError) as e:
            db.session.rollback()
            flash(f'Error updating scenario: Invalid input values')
        except Exception as e:
            db.session.rollback()
            flash('Error updating scenario.')
    
    return render_template('earnings/edit_scenario.html', evaluee=evaluee, scenario=scenario) 