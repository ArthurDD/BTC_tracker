from concurrent.futures import ThreadPoolExecutor
import time
from functools import partial
from requests.exceptions import HTTPError
from bs4 import *
import sys

import requests
import requests_cache


class ChainParser:
    def __init__(self, address, nb_layers):
        self.address = address
        self.nb_layers = nb_layers
        self.wallet_url = f"https://www.walletexplorer.com/address/{address}"
        self.transaction_list = []
        self.transaction_dict = {}
        self.session = requests_cache.CachedSession('parser_cache')
        print(self.wallet_url)

    def retrieve_transaction_ids(self):
        """
        Requests on the wallet page to get all the transactions done to that address, stores the transaction ids in
        self.transaction_list
        :return:
        """
        # test_list = []
        try:
            # TODO: Implement sessions to cache the request results (see requests_cache.CachedSession('demo_cache'))
            req = self.session.get(self.wallet_url)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:
            print('Success!')
            # test_list += [0]
            soup = BeautifulSoup(req.content, 'html.parser')

            nb_pages = soup.find('div', class_='paging').text
            index = nb_pages.find("1 /")
            nb_pages = int(nb_pages[index:].split(" ")[2])
            print(nb_pages)

            page_links = [f"{self.wallet_url}?page={i}" for i in range(1, nb_pages+1)]
            with ThreadPoolExecutor() as executor:
                fn = partial(self._get_txids)  # test_list)

                # Executes fn concurrently using threads on the links iterable. The
                # timeout is for the entire process, not a single call, so downloading
                # all images must complete within 30 seconds.
                executor.map(fn, page_links, timeout=30)

            print(len(self.transaction_list))
            # print("Number of successful requests: ", len(test_list))
            print("Done")
            print(f"Length of list: {len(self.transaction_list)}")
            print(f"Size of list: {sys.getsizeof(self.transaction_list)}")

            print(f"Length of dict: {len(self.transaction_dict)}")
            print(f"Size of dict: {sys.getsizeof(self.transaction_dict)}")
            # print(f"\n\nList of txids: {self.transaction_dict.keys()}")

    def _get_txids(self, link):
        try:
            req = self.session.get(link)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            pass
        except Exception as err:
            pass
            print(f'Other error occurred: {err}')
        else:
            soup = BeautifulSoup(req.content, 'html.parser')
            for elt in soup.find_all(class_="received"):
                tx_amount = elt.find(class_="amount diff").text
                tx_id = elt.find(class_="txid").text

                self.transaction_list += [(tx_id, tx_amount)]
                self.transaction_dict[tx_id] = [tx_amount]


def test_limits():
    ended = False
    while not ended:
        try:
            # TODO: Implement sessions to cache the request results (see requests_cache.CachedSession('demo_cache'))
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