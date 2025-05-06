import subprocess
import sys

def check_dependencies():
    """Check for required dependencies and install them if necessary"""
    required_packages = [
        "apscheduler>=3.11.0",
        "cron-descriptor>=1.4.5",
        "fastapi>=0.115.12",
        "httpx>=0.28.1",
        "icalendar>=5.0.10",
        "jinja2>=3.1.6",
        "python-multipart>=0.0.20",
        "pytz>=2025.2",
        "sqlalchemy>=2.0.40",
        "uvicorn>=0.34.2",
    ]
    
    print("Checking dependencies...\n")
    
    for package in required_packages:
        package_name = package.split(">")[0].split("=")[0].strip()
        try:
            __import__(package_name.replace("-", "_"))
            print(f"\u2713 {package_name} is installed")
        except ImportError:
            print(f"\u2717 Installing {package}...")
            try:
                # Try to use uv first
                subprocess.check_call([sys.executable, "-m", "uv", "pip", "install", package])
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fall back to pip if uv fails
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])

if __name__ == "__main__":
    check_dependencies()
    print("\nAll dependencies installed successfully!")
    print("Now you can run the application with:")
    print("python app.py")
