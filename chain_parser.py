import unicodedata
from concurrent.futures import ThreadPoolExecutor
import time
from functools import partial
from requests.exceptions import HTTPError
from bs4 import *
import sys
from progress.bar import Bar
import requests
import requests_cache


class WEChainParser:
    # TODO: Once all the requests have been made to retrieve input addresses and their respective txid, check if the
    #  addresses have already been clustered. If they have, we stop and "identify" these BTC. If not, we go through
    #  another layer (until we reach our layer limit)
    #  We also need to check whether the coins have been mined or not (if so, identify BTC and stop)
    def __init__(self, address, nb_layers):
        self.address = address
        self.nb_layers = nb_layers
        self.wallet_url = f"https://www.walletexplorer.com/api/1/address?address={address}" \
                          f"&from=0&count=100&caller=arthur"
        self.transaction_lists = {i: [] for i in range(nb_layers + 1)}
        self.session = requests_cache.CachedSession('parser_cache')
        print(self.wallet_url)
        self.layer_counter = 1
        self.remaining_req = 45  # Number of requests that we are still allowed to make before reaching the limit

    def get_wallet_transactions(self):
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
            print('Success! Starting retrieving Tx received from that address')
            nb_tx = req.json()["txs_count"]
            nb_req = nb_tx // 100 if nb_tx % 100 == 0 else nb_tx // 100 + 1
            tot_url_list = [f"https://www.walletexplorer.com/api/1/address?address={self.address}"
                            f"&from={i * 100}&count=100&caller=arthur" for i in range(nb_req)]

            req_counter = 0
            print(f"Number of requests to make: {nb_req}")
            while req_counter < nb_req:
                if req_counter + self.remaining_req > nb_req:
                    url_list = tot_url_list[req_counter:]
                    req_counter += self.remaining_req
                    self.remaining_req -= (nb_req - req_counter)
                else:
                    url_list = tot_url_list[req_counter: self.remaining_req]
                    req_counter += self.remaining_req
                    self.remaining_req = 0

                print(f"Requests done so far: {req_counter}")
                with ThreadPoolExecutor() as executor:
                    fn = partial(self._retrieve_txids)  # test_list)
                    executor.map(fn, url_list, timeout=30)

                self.check_request_limit()

            self.transaction_lists[0].sort(key=lambda x: x[1], reverse=True)

            print(f"Length of list: {len(self.transaction_lists[0])}")
            print(f"Size of list: {sys.getsizeof(self.transaction_lists[0])}")

            print(f"Biggest transactions: {self.transaction_lists[0][:15]}")

    def _retrieve_txids(self, link):
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
            content = req.json()
            for tx in content['txs']:
                if tx["amount_received"] > 0:  # If it is a received transaction and not a sent one
                    self.transaction_lists[0].append((tx["txid"], tx["amount_received"]))

    def get_addresses_from_txid(self):
        """
        Requests every tx page of the current layer to get input addresses of that tx and their respective txid
        :return:
        """
        print(f"RETRIEVING ADDRESSES FROM TXID")
        tot_url_list = [f"https://www.walletexplorer.com/api/1/tx?txid={tx[0]}&caller=arthur" for tx in
                        self.transaction_lists[self.layer_counter - 1]]
        req_counter = 0
        while req_counter < len(tot_url_list):
            if req_counter + self.remaining_req > len(tot_url_list):
                url_list = tot_url_list[req_counter:]
                req_counter += self.remaining_req
                self.remaining_req -= (len(tot_url_list) - req_counter)
            else:
                url_list = tot_url_list[req_counter: self.remaining_req]
                req_counter += self.remaining_req
                self.remaining_req = 0

            with ThreadPoolExecutor() as executor:
                fn = partial(self._get_addresses)  # test_list)

                executor.map(fn, url_list, timeout=30)

            print(f"Requests done so far: {req_counter}")
            self.check_request_limit()

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
            output_addresses = req.json()["in"]
            addresses = [(add["next_tx"], add["amount"], add["address"])
                         for add in output_addresses]
            # (input_txid, amount, input_address) --> Here, input_txid is the txid of the btc in input
            self.transaction_lists[self.layer_counter] += addresses
            # print(self.transaction_lists[self.layer_counter])

    def start_analysis(self):
        self.get_wallet_transactions()

        while self.layer_counter < self.nb_layers:
            self.get_addresses_from_txid()
            self.layer_counter += 1

    def check_request_limit(self):
        """
        Checks if we can still make requests. If we can't, we wait until we can.
        :return:
        """
        if self.remaining_req == 0:
            waiting_bar(10)
            self.remaining_req = 45


def waiting_bar(seconds):
    """
    Loading bar waiting for "seconds" sec
    :param seconds: number of seconds to wait
    :return:
    """
    for _ in Bar('Waiting for request limit', suffix='%(percent)d%%').iter(range(1, seconds + 1)):
        time.sleep(1)


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


