from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..models.models import db, Evaluee, PensionScenario
from datetime import datetime

pension = Blueprint('pension', __name__)

@pension.route('/pension/<int:evaluee_id>')
@login_required
def pension_form(evaluee_id):
    """Display pension analysis form."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    if evaluee.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('evaluee.index'))
    
    scenarios = PensionScenario.query.filter_by(evaluee_id=evaluee_id).order_by(
        PensionScenario.created_at.desc()
    ).all()
    
    return render_template('pension/form.html', 
                         evaluee=evaluee, 
                         scenarios=scenarios)

@pension.route('/pension/<int:evaluee_id>', methods=['POST'])
@login_required
def create_scenario(evaluee_id):
    """Create a new pension scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    if evaluee.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('evaluee.index'))
    
    try:
        scenario = PensionScenario(
            evaluee_id=evaluee_id,
            scenario_name=request.form.get('scenario_name'),
            calculation_method=request.form.get('calculation_method'),
            growth_rate=float(request.form.get('growth_rate')) / 100,  # Convert from percentage
            discount_rate=float(request.form.get('discount_rate')) / 100  # Convert from percentage
        )
        
        if scenario.calculation_method == 'contributions':
            scenario.years_to_retirement = int(request.form.get('years_to_retirement'))
            scenario.annual_contribution = float(request.form.get('annual_contribution'))
        else:  # payments
            scenario.retirement_age = int(request.form.get('retirement_age'))
            scenario.life_expectancy = int(request.form.get('life_expectancy'))
            scenario.annual_pension_benefit = float(request.form.get('annual_pension_benefit'))
        
        # Calculate present value
        scenario.calculate_present_value()
        
        db.session.add(scenario)
        db.session.commit()
        
        flash('Pension scenario created successfully.')
        return redirect(url_for('pension.view_scenario', 
                              evaluee_id=evaluee_id, 
                              scenario_id=scenario.id))
    
    except ValueError as e:
        flash(f'Invalid input: {str(e)}')
    except Exception as e:
        flash('Error creating scenario.')
    
    return redirect(url_for('pension.pension_form', evaluee_id=evaluee_id))

@pension.route('/pension/<int:evaluee_id>/scenario/<int:scenario_id>')
@login_required
def view_scenario(evaluee_id, scenario_id):
    """View a pension scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    if evaluee.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('evaluee.index'))
    
    scenario = PensionScenario.query.get_or_404(scenario_id)
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario.')
        return redirect(url_for('pension.pension_form', evaluee_id=evaluee_id))
    
    return render_template('pension/view_scenario.html',
                         evaluee=evaluee,
                         scenario=scenario)

@pension.route('/pension/<int:evaluee_id>/scenario/<int:scenario_id>/edit', 
              methods=['GET', 'POST'])
@login_required
def edit_scenario(evaluee_id, scenario_id):
    """Edit a pension scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    if evaluee.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('evaluee.index'))
    
    scenario = PensionScenario.query.get_or_404(scenario_id)
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario.')
        return redirect(url_for('pension.pension_form', evaluee_id=evaluee_id))
    
    if request.method == 'POST':
        try:
            scenario.scenario_name = request.form.get('scenario_name')
            scenario.calculation_method = request.form.get('calculation_method')
            scenario.growth_rate = float(request.form.get('growth_rate')) / 100
            scenario.discount_rate = float(request.form.get('discount_rate')) / 100
            
            if scenario.calculation_method == 'contributions':
                scenario.years_to_retirement = int(request.form.get('years_to_retirement'))
                scenario.annual_contribution = float(request.form.get('annual_contribution'))
                # Clear payments fields
                scenario.retirement_age = None
                scenario.life_expectancy = None
                scenario.annual_pension_benefit = None
            else:  # payments
                scenario.retirement_age = int(request.form.get('retirement_age'))
                scenario.life_expectancy = int(request.form.get('life_expectancy'))
                scenario.annual_pension_benefit = float(request.form.get('annual_pension_benefit'))
                # Clear contributions fields
                scenario.years_to_retirement = None
                scenario.annual_contribution = None
            
            # Recalculate present value
            scenario.calculate_present_value()
            
            db.session.commit()
            flash('Scenario updated successfully.')
            return redirect(url_for('pension.view_scenario',
                                  evaluee_id=evaluee_id,
                                  scenario_id=scenario_id))
        
        except ValueError as e:
            flash(f'Invalid input: {str(e)}')
        except Exception as e:
            flash('Error updating scenario.')
    
    return render_template('pension/edit_scenario.html',
                         evaluee=evaluee,
                         scenario=scenario)

@pension.route('/pension/<int:evaluee_id>/scenario/<int:scenario_id>/delete', 
              methods=['POST'])
@login_required
def delete_scenario(evaluee_id, scenario_id):
    """Delete a pension scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    if evaluee.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('evaluee.index'))
    
    scenario = PensionScenario.query.get_or_404(scenario_id)
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario.')
        return redirect(url_for('pension.pension_form', evaluee_id=evaluee_id))
    
    try:
        db.session.delete(scenario)
        db.session.commit()
        flash('Scenario deleted successfully.')
    except Exception as e:
        flash('Error deleting scenario.')
    
    return redirect(url_for('pension.pension_form', evaluee_id=evaluee_id)) 