import concurrent
import random
from concurrent.futures import ThreadPoolExecutor, wait
import time
from functools import partial
from requests.exceptions import HTTPError
import sys
from progress.bar import Bar
import requests
import requests_cache

from transaction import Transaction, find_transaction


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
        self.identified_btc = []
        self.transaction_lists = {i: [] for i in range(nb_layers + 1)}
        self.session = requests_cache.CachedSession('parser_cache')
        self.layer_counter = 0
        self.remaining_req = 45  # Number of requests that we are allowed to make simultaneously
        self.added_before = []

        print(self.wallet_url)

    @staticmethod
    def thread_pool(function, url_list):
        """
        :param function: Either self._get_input_addresses or self._retrieve_txids_from_wallet
        :param url_list: List of URLs to parse
        :return: None
        """
        print("Starting threads")
        with ThreadPoolExecutor() as executor:
            fn = partial(function)
            finished = False
            while not finished:
                finished = True     # Set it to True by default
                futures = [executor.submit(fn, url) for url in url_list]

                done, not_done = wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)

                print(f"Done: {done}")
                print(f"not_done: {not_done}")
                successful_urls = []
                for future in done:  # The failed future has still finished, so we need to catch the exc. raised
                    try:
                        successful_urls.append(future.result())
                    except RequestLimitReached:
                        finished = False
                        print(f"LIMIT REACHED")
                        pass
                    except Exception as err:
                        raise err
                        # print(f"Unexpected error. ({err})")

                print(f"Successful URLS: {successful_urls}")
                # If all the requests were successful or if we got an error that is not the RequestLimitReached,
                # we get out of the while loop
                if not finished:
                    print("Error while making requests (Request limit exceeded). Retrying in 5s...")
                    # Remove all the successful requests
                    url_list = [url for url in url_list if url not in successful_urls]
                    print(f"Length of url_list is now: {len(url_list)}")
                    waiting_bar(15)   # Waiting for the limit to fade

    def get_wallet_transactions(self):
        """
        Requests on the wallet page to get all the transactions done to that address, stores the transaction ids in
        self.transaction_list[0] (we consider the wallet to be layer 0)
        :return: None
        """
        print(f"--------- RETRIEVING TXIDS FROM WALLET ---------\n")
        try:
            req = self.session.get(self.wallet_url)
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'get_wallet_transactions HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'get_wallet_transactions Other error occurred: {err}')
        else:
            nb_tx = req.json()["txs_count"]
            nb_req = nb_tx // 100 if nb_tx % 100 == 0 else nb_tx // 100 + 1
            tot_url_list = [f"https://www.walletexplorer.com/api/1/address?address={self.address}"
                            f"&from={i * 100}&count=100&caller=arthur" for i in range(nb_req)]

            req_counter = 0
            print(f"Number of requests to make: {nb_req}")
            # We make all the requests
            while req_counter < nb_req:
                if req_counter + self.remaining_req > nb_req:
                    url_list = tot_url_list[req_counter:]
                    req_counter += self.remaining_req
                    self.remaining_req -= (nb_req - req_counter) if req_counter < nb_req else nb_req
                else:
                    url_list = tot_url_list[req_counter: self.remaining_req]
                    req_counter += self.remaining_req
                    self.remaining_req = 0

                print(f"Length of url_list: {len(url_list)}")
                self.thread_pool(self._retrieve_txids_from_wallet, url_list)

                if req_counter < nb_req:
                    print(f"Requests done so far: {req_counter}")
                self.check_request_limit()  # If we reached the limit, we pause for a few seconds.

            # Once everything is done, increase layer counter
            self.layer_counter += 1

            self.transaction_lists[0].sort(key=lambda x: x.amount, reverse=True)

            print(f"Length of layer 0: {len(self.transaction_lists[0])}")
            print(f"Size of layer 0: {sys.getsizeof(self.transaction_lists[0])}")
            # print(f"List of tx in layer 0: ")
            # for tx in self.transaction_lists[0]:
            #     print(tx)
            print()

    def _retrieve_txids_from_wallet(self, link):
        """
        Function called by get_wallet_transactions to get the transaction ids from the wallet in input.
        Stores everything in self.transaction_lists[0].
        :param link: Link to make the request to.
        :return: None
        """
        try:
            time.sleep(random.randint(1, 3))
            req = self.session.get(link)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            if "429 Client Error" in str(http_err):
                raise RequestLimitReached(f"Request limit reached. ({http_err})")
            else:
                print(f'FUNCTION HTTP error occurred: {http_err}')
                raise Exception(f"HTTP error occurred: {http_err}")
        except Exception as err:
            raise Exception(f"FUNCTION Other error occurred: {err}")
        else:
            content = req.json()
            for tx in content['txs']:
                if tx["amount_received"] > 0 and tx["amount_sent"] == 0:
                    # If it is a received transaction and not a sent one, and if it's not a payment that he did
                    # re-using his address (change-address = input address)
                    self.transaction_lists[self.layer_counter].append(Transaction(tx['txid'],
                                                                                  output_addresses=[self.address],
                                                                                  amount=tx["amount_received"]))
            return link

    def get_addresses_from_txid(self):
        """
        Requests every tx page of the current layer (from txids stored in transaction_lists[i]) to get input addresses
        of that tx and their respective txid
        :return: None
        """
        print(f"\n\n\n--------- RETRIEVING ADDRESSES FROM TXID LAYER {self.layer_counter}---------\n")
        tot_url_list = [f"https://www.walletexplorer.com/api/1/tx?txid={tx.txid}&caller=arthur"
                        for tx in self.transaction_lists[self.layer_counter - 1]]
        req_counter = 0
        print(f"req_counter: {req_counter}")
        print(f"Number of requests to make: {len(tot_url_list)}")

        # We make sure all the requests are made
        while req_counter < len(tot_url_list):
            if req_counter + self.remaining_req > len(tot_url_list):
                url_list = tot_url_list[req_counter:]
                req_counter += self.remaining_req
                self.remaining_req -= (len(tot_url_list) - req_counter) if req_counter < len(tot_url_list) else len(tot_url_list)
            else:
                url_list = tot_url_list[req_counter: self.remaining_req]
                req_counter += self.remaining_req
                self.remaining_req = 0

            print(f"Length of url_list: {len(url_list)}")
            self.thread_pool(self._get_input_addresses, url_list)

            if req_counter < len(tot_url_list):
                print(f"Requests done so far: {req_counter}")
            self.check_request_limit()

        print(f"\n\nAdded before: {self.added_before}\n\n")
        print(f"Tx of layer {self.layer_counter}:")
        for tx in self.transaction_lists[self.layer_counter]:
            print(tx)

        self.layer_counter += 1

    def _get_input_addresses(self, link):
        """
        Called by get_addresses_from_txid.
        Only used to parse the page at the indicated link. Retrieves BTC input address of a transaction as well as its
        associated txid.
        :param link: url of the page to parse
        :return:
        """
        try:
            time.sleep(random.randint(1, 3))
            req = self.session.get(link)
            req.raise_for_status()
        except HTTPError as http_err:
            if "429 Client Error" in str(http_err):
                raise RequestLimitReached(f"Request limit reached. ({http_err})")
            else:
                raise Exception(f"HTTP error occurred: {http_err}")
        except Exception as err:
            raise Exception(f"Other error occurred: {err}")
        else:
            tx_content = req.json()
            tx_id = link[link.find("txid="):].split("&")[0][5:]
            if tx_content["is_coinbase"]:  # If it's mined bitcoins
                print(f"MINED BITCOINS")
                find_transaction(self.transaction_lists[self.layer_counter - 1], tx_id).tag = "Mined"
            elif "label" in tx_content:  # If the input address has been identified, we add the tag to the tx
                print(f"IDENTIFIED BITCOIN")
                find_transaction(self.transaction_lists[self.layer_counter - 1], tx_id).tag = tx_content['label']
                # We don't need to go through the inputs of this tx as we've already found out where the BTC are from.
            else:
                # print(f"Number of inputs: {len(tx_content['in'])}")
                for add in tx_content['in']:
                    if add['is_standard']:  # To manage the case with OPCODE (see notes)
                        i = find_transaction(self.transaction_lists[self.layer_counter], add["next_tx"])
                        if i == -1:  # Means we have not added that txid to the next layer yet
                            self.transaction_lists[self.layer_counter].append(
                                Transaction(txid=add['next_tx'], prev_txid=tx_id,
                                            amount=add['amount'],
                                            output_addresses=[add['address']]))
                        else:
                            self.added_before.append(add['next_tx'])
                            # print("ADDED BEFORE")
                            self.transaction_lists[self.layer_counter][i].amount += add['amount']
                            if add['address'] not in self.transaction_lists[self.layer_counter][i].output_addresses:
                                self.transaction_lists[self.layer_counter][i].output_addresses.append(add['address'])
            return link

    def analyse_addresses(self, layer_number):
        """
        Go through all the transactions of a layer to check:
        - If BTC have been mined (if it has, stop the crawling for these BTC)
        - If the address has been identified already (might need to make requests to the wallet page)
            --> If it has, we stop the crawling, otherwise, we continue
        :param layer_number: Number of the layer to analyse
        :return: None
        """
        for tx in self.transaction_lists[layer_number]:
            if tx[3]:  # If these BTC have been mined:
                self.identified_btc.append(("Mined", tx[1], tx[0]))

    def start_analysis(self):
        self.get_wallet_transactions()

        while self.layer_counter <= self.nb_layers:
            print(f"Layer counter: {self.layer_counter}")
            self.get_addresses_from_txid()

        print(f"Layer 0: {len(self.transaction_lists[0])}")
        print(f"Layer 1: {len(self.transaction_lists[1])}")
        print(f"Layer 2: {len(self.transaction_lists[2])}")

    def check_request_limit(self):
        """
        Checks if we can still make requests. If we can't, we wait until we can.
        :return:
        """
        if self.remaining_req == 0:
            waiting_bar(5)  # Sleeps 5 seconds
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


class RequestLimitReached(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message