from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class Evaluee(db.Model):
    """Model for storing evaluee information."""
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    uses_discounting = db.Column(db.Boolean, default=True)
    _discount_rates = db.Column('discount_rates', db.Text, default='[3.0, 5.0, 7.0]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Demographics data
    date_of_birth = db.Column(db.DateTime)
    date_of_injury = db.Column(db.DateTime)
    life_expectancy = db.Column(db.Numeric(10, 2))
    work_life_expectancy = db.Column(db.Numeric(10, 2))
    years_to_final_separation = db.Column(db.Numeric(10, 2))
    
    # Worklife factor data
    worklife_factor = db.Column(db.Numeric(10, 4))
    
    # AEF data
    gross_earnings_base = db.Column(db.Numeric(10, 2))
    worklife_adjustment = db.Column(db.Numeric(10, 4))
    unemployment_factor = db.Column(db.Numeric(10, 4))
    fringe_benefit = db.Column(db.Numeric(10, 4))
    tax_liability = db.Column(db.Numeric(10, 4))
    wrongful_death = db.Column(db.Boolean, default=False)
    personal_type = db.Column(db.String(50))
    personal_percentage = db.Column(db.Numeric(10, 4))
    
    # Relationships
    earnings_scenarios = db.relationship('EarningsScenario', backref='evaluee', lazy=True)

    @property
    def discount_rates(self):
        return json.loads(self._discount_rates)
    
    @discount_rates.setter
    def discount_rates(self, value):
        self._discount_rates = json.dumps(value)

class EarningsScenario(db.Model):
    """Model for storing earnings calculation scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    wage_base = db.Column(db.Numeric(10, 2), nullable=False)
    residual_base = db.Column(db.Numeric(10, 2))
    growth_rate = db.Column(db.Numeric(10, 4))
    adjustment_factor = db.Column(db.Numeric(10, 4))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Store calculation results
    present_value = db.Column(db.Numeric(15, 2))
    total_loss = db.Column(db.Numeric(15, 2)) 