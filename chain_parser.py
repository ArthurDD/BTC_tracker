# def request_pool():
#     with ThreadPoolExecutor() as executor:
#         # Create a new partially applied function that stores the directory
#         # argument.
#         #
#         # This allows the download_link function that normally takes two
#         # arguments to work with the map function that expects a function of a
#         # single argument.
#         fn = partial(download_link, download_dir)
#
#         # Executes fn concurrently using threads on the links iterable. The
#         # timeout is for the entire process, not a single call, so downloading
#         # all images must complete within 30 seconds.
#         executor.map(fn, links, timeout=30)
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from requests.exceptions import HTTPError
from bs4 import *

import requests


class ChainParser:
    def __init__(self, address, nb_layers):
        self.address = address
        self.nb_layers = nb_layers
        self.wallet_url = f"https://www.walletexplorer.com/address/{address}"
        self.transaction_list = []
        print(self.wallet_url)

    def retrieve_transaction_ids(self):
        """
        Requests on the wallet page to get all the transactions done to that address, stores the transaction ids in
        self.transaction_list
        :return:
        """
        try:
            # TODO: Implement sessions to cache the request results (see requests_cache.CachedSession('demo_cache'))
            req = requests.get(self.wallet_url)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:
            print('Success!')

            soup = BeautifulSoup(req.content, 'html.parser')
            # print(soup.prettify())
            txids = soup.find_all(class_="txid")
            # print(txids)
            print("\n".join([elt.text for elt in txids]))
            # TODO: Go through all the pages to get all the txids.

    # def make_requests(self):
    #     with ThreadPoolExecutor() as executor:
    #         # Create a new partially applied function that stores the directory
    #         # argument.
    #         #
    #         # This allows the download_link function that normally takes two
    #         # arguments to work with the map function that expects a function of a
    #         # single argument.
    #         fn = partial(download_link, download_dir)
    #
    #         # Executes fn concurrently using threads on the links iterable. The
    #         # timeout is for the entire process, not a single call, so downloading
    #         # all images must complete within 30 seconds.
    #         executor.map(fn, links, timeout=30)
