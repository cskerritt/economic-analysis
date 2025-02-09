# Economic Analysis Application

A Flask-based web application for performing economic analysis calculations, including worklife expectancy, annual earnings factors, and present value calculations.

## Features

- Evaluee Management (Create, Read, Update, Delete)
- Demographics Calculator (anchored at Date of Injury)
- Worklife Factor Calculator
- Annual Earnings Factor (AEF) Calculator
- Earnings Calculator with multi-scenario support
- Support for discounting calculations
- Excel report generation
- Modern, responsive UI with Bootstrap 5

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/economic-analysis.git
cd economic-analysis
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the database:
```bash
flask db upgrade
```

## Configuration

The application supports different environments through configuration classes:

- Development: SQLite database, debug mode enabled
- Production: PostgreSQL database, debug mode disabled
- Testing: In-memory SQLite database

Set the `FLASK_CONFIG` environment variable to choose the configuration:
```bash
export FLASK_CONFIG=development  # or production, testing
```

## Running the Application

1. Development server:
```bash
flask run
```

2. Production server (using gunicorn):
```bash
gunicorn "forensic_econ_app:create_app()"
```

## Project Structure

```
economic-analysis/
├── forensic_econ_app/
│   ├── __init__.py
│   ├── models/
│   │   └── models.py
│   ├── routes/
│   │   ├── evaluee.py
│   │   ├── demographics.py
│   │   ├── worklife.py
│   │   ├── aef.py
│   │   └── earnings.py
│   ├── templates/
│   │   ├── base.html
│   │   └── evaluee/
│   │       ├── index.html
│   │       ├── create.html
│   │       ├── edit.html
│   │       └── view.html
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── main.js
│   ├── utils/
│   │   └── calculations.py
│   └── config/
│       └── config.py
├── migrations/
├── tests/
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

## Development

### Database Migrations

When making changes to the database models:

1. Generate migration:
```bash
flask db migrate -m "Description of changes"
```

2. Apply migration:
```bash
flask db upgrade
```

### Running Tests

```bash
python -m pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Flask and its extensions
- Bootstrap for the UI framework
- All contributors and users of the application 