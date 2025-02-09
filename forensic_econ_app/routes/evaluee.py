from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app
)
from ..models.models import db, Evaluee
from datetime import timedelta

bp = Blueprint('evaluee', __name__)

@bp.route('/')
def index():
    """List all evaluees."""
    evaluees = Evaluee.query.order_by(Evaluee.created_at.desc()).all()
    return render_template('evaluee/index.html', evaluees=evaluees)

@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create a new evaluee."""
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        state = request.form.get('state', '').strip()
        uses_discounting = 'discounting' in request.form
        
        if not all([first_name, last_name, state]):
            flash('All fields are required.')
            return redirect(url_for('evaluee.create'))
        
        # Parse discount rates
        try:
            if uses_discounting:
                rates_str = request.form.get('discount_rates', '3,5,7')
                discount_rates = [float(x.strip()) for x in rates_str.split(',') if x.strip()]
            else:
                discount_rates = [0.0]
        except ValueError:
            flash('Invalid discount rates format. Use comma-separated numbers.')
            return redirect(url_for('evaluee.create'))
        
        evaluee = Evaluee(
            first_name=first_name,
            last_name=last_name,
            state=state,
            uses_discounting=uses_discounting,
            discount_rates=discount_rates
        )
        
        try:
            db.session.add(evaluee)
            db.session.commit()
            flash('Evaluee created successfully.')
            return redirect(url_for('evaluee.view', evaluee_id=evaluee.id))
        except Exception as e:
            current_app.logger.error(f'Error creating evaluee: {str(e)}')
            db.session.rollback()
            flash('An error occurred while creating the evaluee.')
            return redirect(url_for('evaluee.create'))
    
    return render_template('evaluee/create.html')

@bp.route('/<int:evaluee_id>')
def view(evaluee_id):
    """View evaluee details."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    return render_template('evaluee/view.html', evaluee=evaluee, timedelta=timedelta)

@bp.route('/<int:evaluee_id>/edit', methods=['GET', 'POST'])
def edit(evaluee_id):
    """Edit evaluee details."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    
    if request.method == 'POST':
        evaluee.first_name = request.form.get('first_name', '').strip()
        evaluee.last_name = request.form.get('last_name', '').strip()
        evaluee.state = request.form.get('state', '').strip()
        evaluee.uses_discounting = 'discounting' in request.form
        
        if not all([evaluee.first_name, evaluee.last_name, evaluee.state]):
            flash('All fields are required.')
            return redirect(url_for('evaluee.edit', evaluee_id=evaluee_id))
        
        try:
            if evaluee.uses_discounting:
                rates_str = request.form.get('discount_rates', '3,5,7')
                evaluee.discount_rates = [float(x.strip()) for x in rates_str.split(',') if x.strip()]
            else:
                evaluee.discount_rates = [0.0]
        except ValueError:
            flash('Invalid discount rates format. Use comma-separated numbers.')
            return redirect(url_for('evaluee.edit', evaluee_id=evaluee_id))
        
        try:
            db.session.commit()
            flash('Evaluee updated successfully.')
            return redirect(url_for('evaluee.view', evaluee_id=evaluee_id))
        except Exception as e:
            current_app.logger.error(f'Error updating evaluee: {str(e)}')
            db.session.rollback()
            flash('An error occurred while updating the evaluee.')
            return redirect(url_for('evaluee.edit', evaluee_id=evaluee_id))
    
    return render_template('evaluee/edit.html', evaluee=evaluee)

@bp.route('/<int:evaluee_id>/delete', methods=['POST'])
def delete(evaluee_id):
    """Delete an evaluee."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    try:
        db.session.delete(evaluee)
        db.session.commit()
        flash('Evaluee deleted successfully.')
    except Exception as e:
        current_app.logger.error(f'Error deleting evaluee: {str(e)}')
        db.session.rollback()
        flash('An error occurred while deleting the evaluee.')
    
    return redirect(url_for('evaluee.index')) 