import click
from flask.cli import with_appcontext
from .models.models import db, ECECWorkerType, ECECGeographicRegion
from decimal import Decimal

@click.command('init-ecec-data')
@with_appcontext
def init_ecec_data():
    """Initialize ECEC data with default values."""
    # Worker Types
    worker_types = [
        {
            'worker_type': 'Civilian',
            'wages_and_salaries': Decimal('32.25'),
            'total_benefits': Decimal('14.59'),
            'legally_required_benefits': Decimal('7.0')
        },
        {
            'worker_type': 'Private Industry',
            'wages_and_salaries': Decimal('31.25'),
            'total_benefits': Decimal('13.15'),
            'legally_required_benefits': Decimal('7.3')
        },
        {
            'worker_type': 'State & Local Government',
            'wages_and_salaries': Decimal('38.86'),
            'total_benefits': Decimal('24.06'),
            'legally_required_benefits': Decimal('5.3')
        },
        {
            'worker_type': 'Union',
            'wages_and_salaries': Decimal('35.92'),
            'total_benefits': Decimal('23.10'),
            'legally_required_benefits': Decimal('7.3')
        },
        {
            'worker_type': 'Non-Union',
            'wages_and_salaries': Decimal('30.81'),
            'total_benefits': Decimal('12.23'),
            'legally_required_benefits': Decimal('7.3')
        }
    ]
    
    # Geographic Regions
    regions = [
        {
            'region': 'Northeast',
            'wages_and_salaries': Decimal('37.10'),
            'total_benefits': Decimal('16.65')
        },
        {
            'region': 'New England',
            'wages_and_salaries': Decimal('35.68'),
            'total_benefits': Decimal('16.90')
        },
        {
            'region': 'Middle Atlantic',
            'wages_and_salaries': Decimal('37.60'),
            'total_benefits': Decimal('16.57')
        },
        {
            'region': 'South',
            'wages_and_salaries': Decimal('28.33'),
            'total_benefits': Decimal('11.04')
        },
        {
            'region': 'South Atlantic',
            'wages_and_salaries': Decimal('29.58'),
            'total_benefits': Decimal('11.64')
        },
        {
            'region': 'East South Central',
            'wages_and_salaries': Decimal('23.57'),
            'total_benefits': Decimal('8.98')
        },
        {
            'region': 'West South Central',
            'wages_and_salaries': Decimal('28.39'),
            'total_benefits': Decimal('10.96')
        }
    ]
    
    try:
        # Add worker types
        for wt in worker_types:
            if not ECECWorkerType.query.filter_by(worker_type=wt['worker_type']).first():
                worker_type = ECECWorkerType(**wt)
                db.session.add(worker_type)
        
        # Add regions
        for r in regions:
            if not ECECGeographicRegion.query.filter_by(region=r['region']).first():
                region = ECECGeographicRegion(**r)
                db.session.add(region)
        
        db.session.commit()
        click.echo('Successfully initialized ECEC data.')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error initializing ECEC data: {str(e)}', err=True) 