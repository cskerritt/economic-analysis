from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..models.models import db, Evaluee
from ..utils.calculations import calculate_aef

bp = Blueprint('aef', __name__)

@bp.route('/aef/<int:evaluee_id>', methods=['GET', 'POST'])
def form(evaluee_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    calculation_steps = None
    
    if request.method == 'POST':
        evaluee.gross_earnings_base = float(request.form.get('gross_earnings_base'))
        evaluee.worklife_adjustment = float(request.form.get('worklife_adjustment'))
        evaluee.unemployment_factor = float(request.form.get('unemployment_factor'))
        evaluee.fringe_benefit = float(request.form.get('fringe_benefit'))
        evaluee.tax_liability = float(request.form.get('tax_liability'))
        evaluee.wrongful_death = 'wrongful_death' in request.form
        
        if evaluee.wrongful_death:
            evaluee.personal_type = request.form.get('personal_type', '')
            personal_percentage = request.form.get('personal_percentage', '')
            evaluee.personal_percentage = float(personal_percentage) if personal_percentage else 0.0
        else:
            evaluee.personal_type = ''
            evaluee.personal_percentage = 0.0
        
        calculation_steps, _ = calculate_aef(
            evaluee.gross_earnings_base,
            evaluee.worklife_adjustment,
            evaluee.unemployment_factor,
            evaluee.fringe_benefit,
            evaluee.tax_liability,
            evaluee.wrongful_death,
            evaluee.personal_type,
            evaluee.personal_percentage
        )
        
        try:
            db.session.commit()
            flash('AEF calculations updated successfully.')
        except Exception as e:
            db.session.rollback()
            flash('Error updating AEF calculations.')
    
    return render_template('aef/form.html', evaluee=evaluee, evaluee_id=evaluee_id, calculation_steps=calculation_steps) 