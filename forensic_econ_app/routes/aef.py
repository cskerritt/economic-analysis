from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from ..models.models import db, Evaluee
from ..utils.calculations import calculate_aef
import os
from tempfile import mkstemp
import pandas as pd

bp = Blueprint('aef', __name__)

@bp.route('/aef/<int:evaluee_id>', methods=['GET', 'POST'])
def form(evaluee_id):
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    calculation_steps = None
    
    if request.method == 'POST':
        try:
            evaluee.gross_earnings_base = float(request.form.get('gross_earnings_base', 0)) / 100.0
            evaluee.worklife_adjustment = float(request.form.get('worklife_adjustment', 0)) / 100.0
            evaluee.unemployment_factor = float(request.form.get('unemployment_factor', 0)) / 100.0
            evaluee.fringe_benefit = float(request.form.get('fringe_benefit', 0)) / 100.0
            evaluee.tax_liability = float(request.form.get('tax_liability', 0)) / 100.0
            evaluee.wrongful_death = 'wrongful_death' in request.form
            
            if evaluee.wrongful_death:
                evaluee.personal_type = request.form.get('personal_type', '')
                personal_percentage = request.form.get('personal_percentage', '')
                evaluee.personal_percentage = float(personal_percentage) / 100.0 if personal_percentage else 0.0
            else:
                evaluee.personal_type = ''
                evaluee.personal_percentage = 0.0
            
            calculation_steps, final_aef = calculate_aef(
                evaluee.gross_earnings_base,
                evaluee.worklife_adjustment,
                evaluee.unemployment_factor,
                evaluee.fringe_benefit,
                evaluee.tax_liability,
                evaluee.wrongful_death,
                evaluee.personal_type,
                evaluee.personal_percentage
            )
            
            db.session.commit()
            flash('AEF calculations updated successfully.')
        except (ValueError, TypeError) as e:
            db.session.rollback()
            flash(f'Error updating AEF calculations: {str(e)}')
        except Exception as e:
            db.session.rollback()
            flash('Error updating AEF calculations.')
    
    return render_template('aef/form.html', evaluee=evaluee, evaluee_id=evaluee_id, calculation_steps=calculation_steps)

@bp.route('/aef/<int:evaluee_id>/export')
def export_calculations(evaluee_id):
    """Export AEF calculations to Excel."""
    evaluee = Evaluee.query.get_or_404(evaluee_id)
    
    try:
        # Calculate AEF
        calculation_steps, final_aef = calculate_aef(
            evaluee.gross_earnings_base,
            evaluee.worklife_adjustment,
            evaluee.unemployment_factor,
            evaluee.fringe_benefit,
            evaluee.tax_liability,
            evaluee.wrongful_death,
            evaluee.personal_type,
            evaluee.personal_percentage
        )
        
        # Create Excel file
        temp_dir = os.path.dirname(os.path.abspath(__file__))
        temp_path = os.path.join(temp_dir, f'aef_calculations_{evaluee_id}.xlsx')
        
        # Convert calculation steps to DataFrame
        df = pd.DataFrame(calculation_steps)
        
        # Format step names to avoid #NAME? errors
        def format_step_name(x):
            # Wrap in quotes and add equals sign if the step contains special characters or operators
            if any(char in x for char in ['@', '/', '+', '-', '*', '=', ' ']):
                return f'="{x}"'
            return x
            
        df['Step'] = df['Step'].apply(format_step_name)
        
        # Create Excel writer
        with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
            # Write calculation steps
            df.to_excel(writer, sheet_name='AEF Calculations', index=False)
            
            # Get the worksheet
            worksheet = writer.sheets['AEF Calculations']
            
            # Format columns
            worksheet.column_dimensions['A'].width = 40
            worksheet.column_dimensions['B'].width = 15
            
            # Add header with evaluee information
            worksheet.insert_rows(0, 3)
            worksheet['A1'] = f'Annual Earnings Factor Calculation for {evaluee.first_name} {evaluee.last_name}'
            worksheet['A2'] = f'Generated on: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")}'
            
        return send_file(
            temp_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'aef_calculations_{evaluee.last_name}_{evaluee.first_name}.xlsx'
        )
    
    except Exception as e:
        flash(f'Error exporting calculations: {str(e)}')
        return redirect(url_for('aef.form', evaluee_id=evaluee_id))
    
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass 