from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json
import numpy as np
from decimal import Decimal
from typing import List

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Model for user accounts."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Relationship with evaluees
    evaluees = db.relationship('Evaluee', backref='user', lazy=True)
    
    def set_password(self, password):
        """Set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Evaluee(db.Model):
    """Model for storing evaluee information."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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
    
    # Add relationship to offset wages
    offset_wages = db.relationship('OffsetWage', backref='scenario', lazy=True, cascade='all, delete-orphan')

class OffsetWage(db.Model):
    """Model for storing offset wages for specific years in a scenario."""
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('earnings_scenario.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HealthcareScenario(db.Model):
    """Model for storing healthcare expense scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    growth_method = db.Column(db.String(20), default='CPI')  # CPI, PCE, or custom
    growth_rate_custom = db.Column(db.Numeric(10, 4))
    discount_method = db.Column(db.String(20), default='nominal')  # nominal, real, or net
    discount_rate = db.Column(db.Numeric(10, 4))
    partial_offset = db.Column(db.Boolean, default=False)
    total_offset = db.Column(db.Boolean, default=False)
    projection_years = db.Column(db.Integer, default=20)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    medical_items = db.relationship('MedicalItem', backref='scenario', lazy=True, cascade='all, delete-orphan')
    evaluee = db.relationship('Evaluee', backref='healthcare_scenarios', lazy=True)

    def compute_future_medical_costs(self, base_year: int, projection_years: int, inflation_rate: Decimal) -> List[Decimal]:
        """
        Compute future medical costs for each year in the projection period.
        
        Args:
            base_year: The starting year for calculations (e.g., 2023)
            projection_years: Number of years to project into the future
            inflation_rate: Annual inflation rate as a decimal (e.g., 0.03 for 3%)
            
        Returns:
            List of projected costs for each year
        """
        yearly_costs = [Decimal('0')] * projection_years
        
        for item in self.medical_items:
            # Convert to Decimal for precise calculations
            annual_cost = Decimal(str(item.annual_cost))
            
            # Determine the start and end years for this item
            start_idx = item.start_year - 1  # Convert to 0-based index
            if item.duration_years:
                end_idx = start_idx + item.duration_years
            else:
                end_idx = projection_years
            
            # Ensure we don't exceed the projection period
            end_idx = min(end_idx, projection_years)
            
            if start_idx >= projection_years:
                continue  # Skip if the item starts after our projection period
            
            if item.is_one_time:
                # For one-time costs, only apply to the start year
                if start_idx < projection_years:
                    # Apply inflation for the years between base_year and when the cost occurs
                    inflation_factor = (1 + inflation_rate) ** start_idx
                    yearly_costs[start_idx] += annual_cost * inflation_factor
            else:
                # For recurring costs, apply to each year in the duration
                for year in range(start_idx, end_idx):
                    # Apply inflation for each year from the base year
                    inflation_factor = (1 + inflation_rate) ** year
                    yearly_costs[year] += annual_cost * inflation_factor
        
        return yearly_costs

class MedicalItem(db.Model):
    """Medical item or service in a healthcare scenario."""
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('healthcare_scenario.id', ondelete='CASCADE'), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    annual_cost = db.Column(db.Numeric(10, 2), nullable=False)
    is_one_time = db.Column(db.Boolean, default=False)
    growth_rate = db.Column(db.Numeric(5, 4))  # If null, use scenario rate
    age_initiated = db.Column(db.Numeric(5, 2))  # Age when cost begins
    age_through = db.Column(db.Numeric(5, 2))  # Age when cost ends
    start_year = db.Column(db.Integer)  # Year when cost begins (1-based)
    duration_years = db.Column(db.Integer)  # Number of years cost continues
    category = db.Column(db.String(100), default='Uncategorized')  # Category of medical service
    interval_years = db.Column(db.Integer, default=1)  # Interval between occurrences (e.g., every 3 years)

class CPIRate(db.Model):
    """Model for storing universal CPI rates."""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, unique=True)
    rate = db.Column(db.Numeric(10, 4), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_rate(category):
        """Get the rate for a specific CPI category."""
        rate = CPIRate.query.filter_by(category=category).first()
        return float(rate.rate) if rate else None

    def __repr__(self):
        return f'<CPIRate {self.category}: {self.rate}%>'

class ECECWorkerType(db.Model):
    """Model for storing ECEC worker type data."""
    id = db.Column(db.Integer, primary_key=True)
    worker_type = db.Column(db.String(100), nullable=False, unique=True)
    wages_and_salaries = db.Column(db.Numeric(10, 2), nullable=False)
    total_benefits = db.Column(db.Numeric(10, 2), nullable=False)
    legally_required_benefits = db.Column(db.Numeric(10, 4), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_all_types():
        """Get all worker types."""
        return [(wt.worker_type, wt.worker_type) for wt in ECECWorkerType.query.all()]

    @staticmethod
    def get_data(worker_type):
        """Get data for a specific worker type."""
        data = ECECWorkerType.query.filter_by(worker_type=worker_type).first()
        if data:
            return {
                'wages_and_salaries': float(data.wages_and_salaries),
                'total_benefits': float(data.total_benefits),
                'legally_required_benefits': float(data.legally_required_benefits)
            }
        return None

class ECECGeographicRegion(db.Model):
    """Model for storing ECEC geographic region data."""
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(100), nullable=False, unique=True)
    wages_and_salaries = db.Column(db.Numeric(10, 2), nullable=False)
    total_benefits = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_all_regions():
        """Get all geographic regions."""
        return [(r.region, r.region) for r in ECECGeographicRegion.query.all()]

    @staticmethod
    def get_data(region):
        """Get data for a specific region."""
        data = ECECGeographicRegion.query.filter_by(region=region).first()
        if data:
            return {
                'wages_and_salaries': float(data.wages_and_salaries),
                'total_benefits': float(data.total_benefits)
            }
        return None

class FringeBenefitScenario(db.Model):
    """Model for storing fringe benefit calculation scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    worker_type = db.Column(db.String(100), nullable=False)
    annual_salary = db.Column(db.Numeric(10, 2), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    inflation_rate = db.Column(db.Numeric(10, 4), nullable=False)
    years_since_update = db.Column(db.Integer, default=0)
    adjusted_fringe_percentage = db.Column(db.Numeric(10, 4))
    fringe_value = db.Column(db.Numeric(15, 2))
    total_compensation = db.Column(db.Numeric(15, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with Evaluee
    evaluee = db.relationship('Evaluee', backref='fringe_benefit_scenarios', lazy=True)

class HouseholdServicesScenario(db.Model):
    """Model for storing household services calculation scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    area_wage_adjustment = db.Column(db.Numeric(10, 4), nullable=False)
    reduction_percentage = db.Column(db.Numeric(10, 4), nullable=False)
    growth_rate = db.Column(db.Numeric(10, 4), nullable=False)
    discount_rate = db.Column(db.Numeric(10, 4), nullable=False)
    present_value = db.Column(db.Numeric(15, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with Evaluee and Stages
    evaluee = db.relationship('Evaluee', backref='household_services_scenarios', lazy=True)
    stages = db.relationship('HouseholdServiceStage', backref='scenario', lazy=True, cascade='all, delete-orphan')
    
    def calculate_present_value(self):
        """Calculate the present value of household services using the staged valuation model."""
        if not self.stages:
            return Decimal('0.00')
        
        total_pv = Decimal('0.0')
        
        # Sort stages by stage_number
        for stage in sorted(self.stages, key=lambda x: x.stage_number):
            for local_year in range(1, stage.years + 1):
                grown_value = stage.annual_value * (
                    (Decimal('1.0') + self.growth_rate) ** (local_year - 1)
                )
                adjusted_value = grown_value * self.area_wage_adjustment * self.reduction_percentage
                present_value = adjusted_value / (
                    (Decimal('1.0') + self.discount_rate) ** local_year
                )
                total_pv += present_value
        
        return total_pv.quantize(Decimal('0.01'))

class HouseholdServiceStage(db.Model):
    """Model for storing stages within a household services scenario."""
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('household_services_scenario.id'), nullable=False)
    stage_number = db.Column(db.Integer, nullable=False)
    years = db.Column(db.Integer, nullable=False)
    annual_value = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PensionScenario(db.Model):
    """Model for storing pension calculation scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    calculation_method = db.Column(db.String(20), nullable=False)  # 'contributions' or 'payments'
    
    # Common fields
    growth_rate = db.Column(db.Numeric(10, 4), nullable=False)
    discount_rate = db.Column(db.Numeric(10, 4), nullable=False)
    present_value = db.Column(db.Numeric(15, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Lost Contributions fields
    years_to_retirement = db.Column(db.Integer)
    annual_contribution = db.Column(db.Numeric(10, 2))
    
    # Lost Pension Payments fields
    retirement_age = db.Column(db.Integer)
    life_expectancy = db.Column(db.Integer)
    annual_pension_benefit = db.Column(db.Numeric(10, 2))
    
    # Relationship with Evaluee
    evaluee = db.relationship('Evaluee', backref='pension_scenarios', lazy=True)
    
    def calculate_present_value(self):
        """Calculate the present value of pension benefits."""
        if self.calculation_method == 'contributions':
            years_array = np.arange(1, self.years_to_retirement + 1)
            annual_contribution = float(self.annual_contribution)
            growth_rate = float(self.growth_rate)
            discount_rate = float(self.discount_rate)
            
            pv = np.sum((annual_contribution * (1 + growth_rate) ** years_array) / 
                       (1 + discount_rate) ** years_array)
        
        elif self.calculation_method == 'payments':
            years_array = np.arange(self.retirement_age, self.life_expectancy + 1)
            pension_benefit = float(self.annual_pension_benefit)
            growth_rate = float(self.growth_rate)
            discount_rate = float(self.discount_rate)
            
            pv = np.sum((pension_benefit * (1 + growth_rate) ** (years_array - self.retirement_age)) / 
                       (1 + discount_rate) ** (years_array - self.retirement_age))
        
        self.present_value = Decimal(str(pv))
        return self.present_value 