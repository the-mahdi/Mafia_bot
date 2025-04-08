import logging
import os

class ApplicationFilter(logging.Filter):
    def __init__(self, application_name):
        super().__init__()
        self.application_name = application_name

    def filter(self, record):
        # Allow logs from the application and the specified error handler
        if record.name.startswith(self.application_name) or record.name == "Mafia Bot ErrorHandler":
            return True

        # Optionally, suppress logs from specific noisy libraries
        if record.name.startswith("telegram") or record.name.startswith("httpx"):
            return False

        return False  # Default to filtering out other logs

def setup_logging():
    # Configure the root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join("logs", "mafia_bot.log"))
        ]
    )

    # Add the filter to the handlers of the root logger
    for handler in logging.getLogger().handlers:
        handler.addFilter(ApplicationFilter("Mafia Bot"))

    logger = logging.getLogger("Mafia Bot")
    return logger