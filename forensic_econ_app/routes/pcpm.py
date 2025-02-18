from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from ..utils.pcpm_calculator import get_pcpm_percentage

bp = Blueprint('pcpm', __name__)

@bp.route('/pcpm/calculate', methods=['POST'])
@login_required
def calculate():
    """Calculate personal consumption/maintenance percentage."""
    try:
        data = request.get_json()
        income = float(data.get('income', 0))
        sex = data.get('sex', '').lower()
        household_size = int(data.get('household_size', 0))
        measure = data.get('measure', 'PC').upper()
        estimate = data.get('estimate', 'high').lower()

        percentage = get_pcpm_percentage(
            income=income,
            sex=sex,
            household_size=household_size,
            measure=measure,
            estimate=estimate
        )

        return jsonify({
            'success': True,
            'percentage': round(percentage, 2),
            'message': f'The {measure} percentage is {percentage:.2f}%'
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred during calculation.'}), 500 