from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required
from ..models.models import db, Evaluee, ECECWorkerType, ECECGeographicRegion, FringeBenefitScenario
from decimal import Decimal, InvalidOperation
from datetime import datetime

bp = Blueprint('fringe_benefits', __name__)

@bp.route('/fringe-benefits/<int:evaluee_id>', methods=['GET', 'POST'])
@login_required
def form(evaluee_id):
    """Display fringe benefits form for an evaluee."""
    current_app.logger.debug(f'Accessing fringe benefits form for evaluee {evaluee_id}')
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenarios = FringeBenefitScenario.query.filter_by(evaluee_id=evaluee_id).all()
    current_app.logger.debug(f'Found {len(scenarios)} scenarios for evaluee')
    
    # Get worker types and regions for dropdowns
    worker_types = ECECWorkerType.get_all_types()
    regions = ECECGeographicRegion.get_all_regions()
    current_app.logger.debug(f'Available worker types: {worker_types}')
    current_app.logger.debug(f'Available regions: {regions}')
    
    if request.method == 'POST':
        try:
            # Get form data
            worker_type = request.form.get('worker_type')
            annual_salary = Decimal(request.form.get('annual_salary'))
            region = request.form.get('region')
            inflation_rate = Decimal(request.form.get('inflation_rate', '0')) / Decimal('100')
            years_since_update = int(request.form.get('years_since_update', '0'))
            
            # Calculate fringe benefits
            worker_data = ECECWorkerType.get_data(worker_type)
            region_data = ECECGeographicRegion.get_data(region)
            
            if not worker_data or not region_data:
                raise ValueError("Invalid worker type or region")
            
            # Convert worker data to Decimal
            wages_and_salaries = Decimal(str(worker_data['wages_and_salaries']))
            total_benefits = Decimal(str(worker_data['total_benefits']))
            legally_required_benefits = Decimal(str(worker_data['legally_required_benefits']))
            
            # Convert region data to Decimal
            region_wages = Decimal(str(region_data['wages_and_salaries']))
            region_benefits = Decimal(str(region_data['total_benefits']))
            
            # Calculate base fringe percentage
            base_fringe_pct = (total_benefits / wages_and_salaries) * Decimal('100')
            
            # Subtract legally required benefits
            adjusted_fringe_pct = base_fringe_pct - legally_required_benefits
            
            # Apply geographic adjustment
            geo_fringe_pct = (region_benefits / region_wages) * Decimal('100')
            geo_factor = geo_fringe_pct / Decimal('45.24')  # National average
            adjusted_fringe_pct *= geo_factor
            
            # Apply inflation adjustment
            if inflation_rate > 0 and years_since_update > 0:
                inflation_factor = (Decimal('1') + inflation_rate) ** years_since_update
                adjusted_fringe_pct *= inflation_factor
            
            # Calculate fringe value and total compensation
            fringe_value = (adjusted_fringe_pct / Decimal('100')) * annual_salary
            total_compensation = annual_salary + fringe_value
            
            # Create new scenario
            scenario = FringeBenefitScenario(
                evaluee_id=evaluee_id,
                scenario_name=request.form.get('scenario_name'),
                worker_type=worker_type,
                annual_salary=annual_salary,
                region=region,
                inflation_rate=inflation_rate,
                years_since_update=years_since_update,
                adjusted_fringe_percentage=adjusted_fringe_pct,
                fringe_value=fringe_value,
                total_compensation=total_compensation
            )
            
            db.session.add(scenario)
            db.session.commit()
            
            flash('Fringe benefit scenario created successfully.', 'success')
            return redirect(url_for('fringe_benefits.view_scenario', evaluee_id=evaluee_id, scenario_id=scenario.id))
            
        except (ValueError, TypeError, InvalidOperation) as e:
            flash(f'Error creating scenario: {str(e)}', 'error')
            current_app.logger.error(f'Error creating fringe benefit scenario: {str(e)}')
        except Exception as e:
            db.session.rollback()
            flash('Error creating fringe benefit scenario.', 'error')
            current_app.logger.error(f'Unexpected error creating fringe benefit scenario: {str(e)}')
    
    return render_template('fringe_benefits/form.html',
                         evaluee=evaluee,
                         scenarios=scenarios,
                         worker_types=worker_types,
                         regions=regions)

@bp.route('/fringe-benefits/<int:evaluee_id>/scenario/<int:scenario_id>')
@login_required
def view_scenario(evaluee_id, scenario_id):
    """View a fringe benefit scenario."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    scenario = FringeBenefitScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('fringe_benefits.form', evaluee_id=evaluee_id))
    
    return render_template('fringe_benefits/view_scenario.html',
                         evaluee=evaluee,
                         scenario=scenario)

@bp.route('/fringe-benefits/<int:evaluee_id>/scenario/<int:scenario_id>/delete', methods=['POST'])
@login_required
def delete_scenario(evaluee_id, scenario_id):
    """Delete a fringe benefit scenario."""
    scenario = FringeBenefitScenario.query.get_or_404(scenario_id)
    
    if scenario.evaluee_id != evaluee_id:
        flash('Invalid scenario for this evaluee.', 'error')
        return redirect(url_for('fringe_benefits.form', evaluee_id=evaluee_id))
    
    try:
        db.session.delete(scenario)
        db.session.commit()
        flash('Fringe benefit scenario deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting scenario.', 'error')
    
    return redirect(url_for('fringe_benefits.form', evaluee_id=evaluee_id))

@bp.route('/fringe-benefits/manage-data', methods=['GET', 'POST'])
@login_required
def manage_data():
    """Manage ECEC data and geographic adjustments."""
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            
            if action == 'add_worker_type':
                worker_type = ECECWorkerType(
                    worker_type=request.form.get('worker_type'),
                    wages_and_salaries=Decimal(request.form.get('wages_and_salaries')),
                    total_benefits=Decimal(request.form.get('total_benefits')),
                    legally_required_benefits=Decimal(request.form.get('legally_required_benefits'))
                )
                db.session.add(worker_type)
                
            elif action == 'add_region':
                region = ECECGeographicRegion(
                    region=request.form.get('region'),
                    wages_and_salaries=Decimal(request.form.get('wages_and_salaries')),
                    total_benefits=Decimal(request.form.get('total_benefits'))
                )
                db.session.add(region)
            
            db.session.commit()
            flash('Data updated successfully.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating data: {str(e)}', 'error')
    
    worker_types = ECECWorkerType.query.all()
    regions = ECECGeographicRegion.query.all()
    
    return render_template('fringe_benefits/manage_data.html',
                         worker_types=worker_types,
                         regions=regions) 