from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..models.models import db, Evaluee
from datetime import datetime

bp = Blueprint('demographics', __name__)

@bp.route('/demographics/<int:evaluee_id>', methods=['GET', 'POST'])
def form(evaluee_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    
    if request.method == 'POST':
        evaluee.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d')
        evaluee.date_of_injury = datetime.strptime(request.form.get('date_of_injury'), '%Y-%m-%d')
        evaluee.life_expectancy = float(request.form.get('life_expectancy'))
        evaluee.work_life_expectancy = float(request.form.get('work_life_expectancy'))
        evaluee.years_to_final_separation = float(request.form.get('years_to_final_separation'))
        
        try:
            db.session.commit()
            flash('Demographics updated successfully.')
            return redirect(url_for('evaluee.view', evaluee_id=evaluee_id))
        except Exception as e:
            db.session.rollback()
            flash('Error updating demographics.')
            return redirect(url_for('demographics.form', evaluee_id=evaluee_id))
    
    return render_template('demographics/form.html', evaluee=evaluee, evaluee_id=evaluee_id) 