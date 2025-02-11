from flask import Blueprint, render_template, redirect, url_for, flash, request
from forensic_econ_app.models.models import db, CPIRate
from decimal import Decimal

settings = Blueprint('settings', __name__)

@settings.route('/settings/cpi-rates')
def manage_cpi_rates():
    """Manage universal CPI rates."""
    rates = CPIRate.query.all()
    return render_template('settings/cpi_rates.html', rates=rates)

@settings.route('/settings/cpi-rates/update', methods=['POST'])
def update_cpi_rates():
    """Update CPI rates."""
    try:
        for category in ['CPI', 'PCE', 'Medical_CPI']:
            rate_value = Decimal(request.form.get(f'{category}_rate', '0')) / 100
            rate = CPIRate.query.filter_by(category=category).first()
            
            if rate:
                rate.rate = rate_value
            else:
                rate = CPIRate(
                    category=category,
                    rate=rate_value,
                    description=request.form.get(f'{category}_description', '')
                )
                db.session.add(rate)
        
        db.session.commit()
        flash('CPI rates updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating CPI rates: {str(e)}', 'error')
    
    return redirect(url_for('settings.manage_cpi_rates')) 