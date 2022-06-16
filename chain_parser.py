import unicodedata
from concurrent.futures import ThreadPoolExecutor
import time
from functools import partial
from requests.exceptions import HTTPError
from bs4 import *
import sys

import requests
import requests_cache


# TODO: Access transaction page thanks to their IDs, and parse sender address with their corresponding amount.
#  Store it somewhere while keeping track on what layer it is.


class ChainParser:
    def __init__(self, address, nb_layers):
        self.address = address
        self.nb_layers = nb_layers
        self.wallet_url = f"https://www.walletexplorer.com/address/{address}"
        self.transaction_lists = {i: [] for i in range(nb_layers + 1)}
        self.session = requests_cache.CachedSession('parser_cache')
        print(self.wallet_url)
        self.layer_counter = 1

    def retrieve_transaction_ids(self):
        """
        Requests on the wallet page to get all the transactions done to that address, stores the transaction ids in
        self.transaction_list
        :return:
        """
        try:
            req = self.session.get(self.wallet_url)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:
            print('Success!')
            soup = BeautifulSoup(req.content, 'html.parser')

            nb_pages = soup.find('div', class_='paging').text
            index = nb_pages.find("1 /")
            nb_pages = int(nb_pages[index:].split(" ")[2])
            print(nb_pages)

            page_links = [f"{self.wallet_url}?page={i}" for i in range(1, nb_pages + 1)]
            with ThreadPoolExecutor() as executor:
                fn = partial(self._get_txids)  # test_list)

                # Executes fn concurrently using threads on the links iterable. The
                # timeout is for the entire process, not a single call, so downloading
                # all images must complete within 30 seconds.
                executor.map(fn, page_links, timeout=30)

            self.transaction_lists[0].sort(key=lambda x: x[1], reverse=True)

            print(len(self.transaction_lists[0]))
            # print("Number of successful requests: ", len(test_list))
            print("Done")
            print(f"Length of list: {len(self.transaction_lists[0])}")
            print(f"Size of list: {sys.getsizeof(self.transaction_lists[0])}")

            print(f"Biggest transactions: {self.transaction_lists[0][:15]}")

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
                tx_amount = float(elt.find(class_="amount diff").text.strip())
                tx_id = elt.find(class_="txid").text

                self.transaction_lists[0].append((tx_id, tx_amount))

    def get_addresses_from_txid(self):
        url_list = [f"https://www.walletexplorer.com/txid/{tx[0]}" for tx in self.transaction_lists[self.layer_counter -1]]
        with ThreadPoolExecutor() as executor:
            fn = partial(self._get_addresses)  # test_list)

            # Executes fn concurrently using threads on the links iterable. The
            # timeout is for the entire process, not a single call, so downloading
            # all images must complete within 30 seconds.
            executor.map(fn, url_list, timeout=30)
        print(self.transaction_lists[self.layer_counter], "\n\n")
        print(f"Layer 0: {len(self.transaction_lists[0])}")
        print(f"Layer 1: {len(self.transaction_lists[1])}")

    def _get_addresses(self, link):
        """
        Only used to parse the page at the indicated link. Retrieves BTC input address of a transaction as well as its
        associated txid.
        :param link: url of the page to parse
        :return:
        """
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
            addresses = []
            for address in soup.find('table', class_="empty").find_all('tr'):
                elt = address.find_all('td')
                # print(elt[2].find('a')['href'].strip().split('/'))
                addresses.append((elt[2].find('a')['href'].strip().split('/')[2],
                                  float(unicodedata.normalize("NFKD", elt[1].text).split(' ')[0]),
                                  elt[0].find('a').text))
                # (input_txid, amount, input_address) --> Here, input_txid is the txid of the btc in input
            self.transaction_lists[self.layer_counter] = addresses
            # print(self.transaction_lists[self.layer_counter])

    def start_analysis(self):
        self.retrieve_transaction_ids()

        while self.layer_counter < self.nb_layers:
            self.get_addresses_from_txid()
            self.layer_counter += 1


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
