from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from ..models.models import db, Evaluee, EarningsScenario
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

@bp.route('/earnings/<int:evaluee_id>/scenario/<int:scenario_id>')
def view_scenario(evaluee_id, scenario_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = EarningsScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.')
        return redirect(url_for('earnings.form', evaluee_id=evaluee_id))
    
    raw_table, display_table, total_pv, total_loss = compute_earnings_table(
        scenario.start_date,
        scenario.end_date,
        float(scenario.wage_base),
        float(scenario.residual_base),
        float(scenario.growth_rate),  # Already stored as decimal in database
        float(evaluee.discount_rates[0] / 100) if evaluee.uses_discounting else 0,
        float(scenario.adjustment_factor),
        evaluee.date_of_birth
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