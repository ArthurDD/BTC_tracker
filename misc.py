import requests
from requests.exceptions import HTTPError
import time


def test_limits():
    ended = False
    while not ended:
        try:
            req = requests.get("https://www.walletexplorer.com/address/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            time.sleep(10)
        except Exception as err:
            pass
        else:
            ended = True

