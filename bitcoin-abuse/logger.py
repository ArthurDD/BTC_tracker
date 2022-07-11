import sys
import traceback
from datetime import datetime


log_folder = "bitcoin-abuse/logs"


class ErrorLogger:

    def __init__(self, logger):
        self.stderr = sys.stderr
        self.logger = logger

    def write(self, message):
        self.logger.file_log(message)
        self.stderr.write(message)

    def flush(self):
        pass


class Logger:

    def __init__(self, folder_id="1fgApxbn1lckOqJSgp1H1yqXrVw6Sf1Yg"):
        date_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        self.folder_id = folder_id
        self.log_name = f"BA_log_{date_time}.txt"
        self.log_location = f"{log_folder}/{self.log_name}"
        self.log = open(self.log_location, "w")
        self.stdout = sys.stdout

    def get_log_name(self):
        return self.log_name

    def terminate(self):
        self.log.flush()

    def file_log(self, message):
        self.log.write(message)

    def write(self, message):
        self.file_log(message)
        self.stdout.write(message)

    def flush(self):
        self.log.flush()


if __name__ == '__main__':
    sys.stdout = Logger()
    sys.stderr = ErrorLogger(sys.stdout)
    try:
        print("I am the Senate")
        print("Synchro Tensei")
    except:
        traceback.print_exc(file=sys.stderr)
    sys.stdout.terminate()
