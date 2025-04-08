from src.core.logging_config import setup_logging
from src.core.application import setup_application, run_application

def main():
    # Setup logging 
    setup_logging()
    
    # Setup and run the application
    application = setup_application()
    run_application(application)

if __name__ == "__main__":
    main()
