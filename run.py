#!/usr/bin/env python3
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

# Define the application directory name
APP_DIR = "EconomicAnalysis"

def find_app_directory():
    """Find the application directory from anywhere in the system."""
    # First check if we're already in the correct directory
    current = Path.cwd()
    if current.name == APP_DIR:
        return current
    
    # Check if it's in the home directory
    home = Path.home()
    app_path = home / APP_DIR
    if app_path.exists():
        return app_path
    
    # If not found, ask user for location
    print(f"Could not find {APP_DIR} directory.")
    while True:
        path_input = input(f"Please enter the full path to your {APP_DIR} directory: ").strip()
        path = Path(os.path.expanduser(path_input))
        if path.exists() and path.name == APP_DIR:
            return path
        print("Invalid directory. Please try again.")

def create_venv():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path('.venv')
    if not venv_path.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
        return True
    return False

def get_venv_python():
    """Get the path to the virtual environment Python executable."""
    if sys.platform == 'win32':
        python_path = '.venv/Scripts/python.exe'
    else:
        python_path = '.venv/bin/python'
    return str(Path(python_path).absolute())

def get_venv_pip():
    """Get the path to the virtual environment pip executable."""
    if sys.platform == 'win32':
        pip_path = '.venv/Scripts/pip.exe'
    else:
        pip_path = '.venv/bin/pip'
    return str(Path(pip_path).absolute())

def install_requirements():
    """Install requirements in the virtual environment."""
    print("Installing requirements...")
    pip_path = get_venv_pip()
    
    # First upgrade pip
    print("Upgrading pip...")
    subprocess.run([pip_path, 'install', '--upgrade', 'pip'], check=True)
    
    # Install numpy first
    print("Installing numpy...")
    subprocess.run([pip_path, 'install', 'numpy'], check=True)
    
    # Then install pandas
    print("Installing pandas...")
    subprocess.run([pip_path, 'install', 'pandas'], check=True)
    
    # Finally install all other requirements
    print("Installing other requirements...")
    subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)

def init_database():
    """Initialize the database if it doesn't exist."""
    instance_dir = Path('instance')
    if not instance_dir.exists():
        print("Creating instance directory...")
        instance_dir.mkdir()
        
    if not Path('instance/dev.db').exists():
        print("Initializing database...")
        python_path = get_venv_python()
        
        # Set up environment variables
        env = {
            **os.environ,
            'FLASK_APP': 'app.py',
            'FLASK_ENV': 'development'
        }
        
        # Run database initialization
        subprocess.run([python_path, '-m', 'flask', 'db', 'upgrade'], 
                      env=env, check=True)

def run_application():
    """Run the Flask application and open it in the browser."""
    python_path = get_venv_python()
    
    # Set up environment variables
    env = {
        **os.environ,
        'FLASK_APP': 'app.py',
        'FLASK_ENV': 'development',
        'PYTHONPATH': str(Path.cwd())
    }
    
    # Start the Flask application in the background
    print("Starting the application...")
    flask_process = subprocess.Popen([
        python_path, '-m', 'flask', 'run', '--debug'
    ], env=env)
    
    # Wait a moment for the server to start
    time.sleep(2)
    
    # Open the browser
    print("Opening browser...")
    webbrowser.open('http://127.0.0.1:5000')
    
    try:
        # Wait for the process to complete or user interrupt
        flask_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down the application...")
        flask_process.terminate()
        flask_process.wait()

def main():
    """Main function to set up and run the application."""
    try:
        # Find and change to the application directory
        app_dir = find_app_directory()
        os.chdir(app_dir)
        print(f"Running from: {app_dir}")
        
        # Create virtual environment if needed
        is_new_venv = create_venv()
        
        # Install requirements if it's a new venv
        if is_new_venv:
            install_requirements()
        
        # Initialize database if needed
        init_database()
        
        # Run the application
        run_application()
        
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 