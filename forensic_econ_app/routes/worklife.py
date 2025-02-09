from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..models.models import db, Evaluee
from ..utils.calculations import calculate_worklife_factor

bp = Blueprint('worklife', __name__)

@bp.route('/worklife/<int:evaluee_id>', methods=['GET', 'POST'])
def form(evaluee_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    
    if request.method == 'POST':
        work_life_expectancy = float(request.form.get('work_life_expectancy'))
        years_to_final_separation = float(request.form.get('years_to_final_separation'))
        
        worklife_factor = calculate_worklife_factor(work_life_expectancy, years_to_final_separation)
        if worklife_factor:
            evaluee.work_life_expectancy = work_life_expectancy
            evaluee.years_to_final_separation = years_to_final_separation
            evaluee.worklife_factor = worklife_factor
            db.session.commit()
            flash('Worklife factor calculated successfully.')
        else:
            flash('Error calculating worklife factor. Please check your inputs.')
        
        return redirect(url_for('evaluee.view', evaluee_id=evaluee_id))
    
    return render_template('worklife/form.html', evaluee=evaluee, evaluee_id=evaluee_id) 