import concurrent
import math
import random
from concurrent.futures import ThreadPoolExecutor, wait
import time
from datetime import timedelta
from functools import partial
from requests.exceptions import HTTPError
import sys
from progress.bar import Bar
# import requests
import requests_cache
from request_limit_reached import RequestLimitReached

from transaction import Transaction, find_transaction


class WEChainParser:
    # TODO: Once all the requests have been made to retrieve input addresses and their respective txid, check if the
    #  addresses have already been clustered. If they have, we stop and "identify" these BTC. If not, we go through
    #  another layer (until we reach our layer limit)
    #  We also need to check whether the coins have been mined or not (if so, identify BTC and stop)
    def __init__(self, address, nb_layers):
        self.address = address
        self.nb_layers = nb_layers
        self.wallet_url = f"http://www.walletexplorer.com/api/1/address?address={address}" \
                          f"&from=0&count=100&caller=3"
        self.identified_btc = []
        self.transaction_lists = {i: [] for i in range(nb_layers + 1)}
        self.session = requests_cache.CachedSession('parser_cache',
                                                    use_cache_dir=True,                # Save files in the default user cache dir
                                                    cache_control=True,                # Use Cache-Control headers for expiration, if available
                                                    expire_after=timedelta(days=14),    # Otherwise expire responses after one day)
                                                    )
        self.layer_counter = 0
        self.remaining_req = 45  # Number of requests that we are allowed to make simultaneously
        self.added_before = []

        # self.proxy_list = []
        # self.proxy_used = []

        # self.read_proxy_list()  # Reads the proxies in http_proxies.txt
        # self.change_session_proxy()  # Initialises the session proxy
        # self.session.proxies = {
        #     'http': 'http://20.110.214.83:80',
        #     'https': 'https://20.110.214.83:80',
        # }
        print(self.wallet_url)

    def thread_pool(self, function, url_list):
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
                finished = True  # Set it to True by default
                futures = [executor.submit(fn, url) for url in url_list]

                # Wait for the first exception to occur
                print(f"Allocating the tasks...")
                done, not_done = wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)

                print(f"Length of Done: {len(done)}")
                print(f"not_done: {len(not_done)}")
                successful_urls = []
                nb_tries = 5
                for future in done:  # The failed future has still finished, so we need to catch the exc. raised
                    try:
                        successful_urls.append(future.result())
                    except RequestLimitReached:
                        print("LIMIT REACHED")
                        finished = False
                        pass
                    except Exception as err:
                        if nb_tries == 0:
                            raise err
                        else:
                            finished = False
                            nb_tries -= 1
                            print(f"Requests failed. ({err})\n {nb_tries} tries left.")
                            pass
                        # print(f"Unexpected error. ({err})")

                print(f"Length of successful URLs: {len(successful_urls)}")
                # If all the requests were successful or if we got an error that is not the RequestLimitReached,
                # we get out of the while loop
                if not finished:
                    print("Error while making requests (Request limit exceeded). Retrying in 5s...")
                    # Remove all the successful requests
                    url_list = [url for url in url_list if url not in successful_urls]
                    print(f"Length of url_list is now: {len(url_list)}")

                    # self.change_session_proxy()  # Change the proxy of the session (and potentially wait for 60s)
                    self.session.close()
                    waiting_bar(30)   # Waiting for the limit to fade
                    self.session = requests_cache.CachedSession('parser_cache')

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
        except Exception as err:
            print(f'get_wallet_transactions - Error occurred: {err}')
        else:
            print(req.json())
            nb_tx = req.json()["txs_count"]
            nb_req = nb_tx // 100 if nb_tx % 100 == 0 else nb_tx // 100 + 1
            tot_url_list = [f"http://www.walletexplorer.com/api/1/address?address={self.address}"
                            f"&from={i * 100}&count=100&caller=paulo" for i in range(nb_req)]

            req_counter = 0
            print(f"Number of requests to make: {nb_req}")

            print(f"Length of url_list: {len(tot_url_list)}")
            self.thread_pool(self._retrieve_txids_from_wallet, tot_url_list)

            # Once everything is done, increase layer counter
            self.layer_counter += 1

            self.transaction_lists[0].sort(key=lambda x: x.amount, reverse=True)

            print(f"Length of layer 0: {len(self.transaction_lists[0])}")
            print(f"Size of layer 0: {sys.getsizeof(self.transaction_lists[0])}")
            print()

    def _retrieve_txids_from_wallet(self, link):
        """
        Function called by get_wallet_transactions to get the transaction ids from the wallet in input.
        Stores everything in self.transaction_lists[0].
        :param link: Link to make the request to.
        :return: None
        """
        try:
            time.sleep(random.random())
            req = self.session.get(link)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except Exception as err:
            if "429 Client Error" in str(err):
                raise RequestLimitReached(f"Request limit reached. ({err})")
            else:
                print(f'retrieve_txids_from_wallet - Error occurred: {err}')
                raise Exception(f"Error occurred: {err}")
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
        tot_url_list = [f"http://www.walletexplorer.com/api/1/tx?txid={tx.txid}&caller=paulo"
                        for tx in self.transaction_lists[self.layer_counter - 1]]
        req_counter = 0
        print(f"req_counter: {req_counter}")
        print(f"Number of requests to make: {len(tot_url_list)}")

        print(f"Length of url_list: {len(tot_url_list)}")
        self.thread_pool(self._get_input_addresses, tot_url_list)

        print(f"\n\nAdded before: {self.added_before}\n\n")
        print(f"Tx of layer {self.layer_counter}:")
        for tx in self.transaction_lists[self.layer_counter][:15]:
            print(tx)
        print("...")
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
            time.sleep(random.random())
            req = self.session.get(link)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except Exception as err:
            if "429 Client Error" in str(err):
                raise RequestLimitReached(f"Request limit reached. ({err})")
            else:
                print(f'retrieve_txids_from_wallet - Error occurred: {err}')
                raise Exception(f"Error occurred: {err}")
        else:
            tx_content = req.json()
            txid = link[link.find("txid="):].split("&")[0][5:]
            # print(f"Link: {link}")
            # print(tx_content)
            if tx_content["is_coinbase"]:  # If it's mined bitcoins
                print(f"MINED BITCOINS")
                i = find_transaction(self.transaction_lists[self.layer_counter - 1], txid)
                self.transaction_lists[self.layer_counter - 1][i].tag = "Mined"
            elif "label" in tx_content:  # If the input address has been identified, we add the tag to the tx
                print(f"IDENTIFIED BITCOIN")
                i = find_transaction(self.transaction_lists[self.layer_counter - 1], txid)
                self.transaction_lists[self.layer_counter - 1][i].tag = tx_content['label']
                # We don't need to go through the inputs of this tx as we've already found out where the BTC are from.
            else:
                # print(f"Number of inputs before pruning: {len(tx_content['in'])}")
                # We select the inputs that we want to keep
                if len(tx_content['in']) > 1:  # and len(tx_content['out']) > 1:
                    selected_inputs = self.select_inputs(tx_content, txid)
                else:
                    selected_inputs = tx_content['in']

                for add in selected_inputs:
                    if add['is_standard']:  # To manage the case with OPCODE (see notes)
                        i = find_transaction(self.transaction_lists[self.layer_counter], add["next_tx"])
                        if i == -1:  # Means we have not added that txid to the next layer yet
                            self.transaction_lists[self.layer_counter].append(
                                Transaction(txid=add['next_tx'], prev_txid=txid,
                                            amount=add['amount'],
                                            output_addresses=[add['address']],
                                            is_special=add['special'] if 'special' in add else None))
                        else:
                            self.added_before.append(add['next_tx'])
                            # print("ADDED BEFORE")
                            self.transaction_lists[self.layer_counter][i].amount += add['amount']
                            if add['address'] not in self.transaction_lists[self.layer_counter][i].output_addresses:
                                self.transaction_lists[self.layer_counter][i].output_addresses.append(add['address'])
            return link

    def select_inputs(self, tx_content, txid):
        """
        Selects inputs that we will continue to investigate. Refer to the decision tree to have a better understanding
        on how we decided to handle the different cases
        :param txid: Transaction ID
        :param tx_content: Content of the transaction that we are currently looking.
        :return: selected input addresses
        """

        # We sort in and out lists as it will be necessary in a further step
        tx_content['in'].sort(key=lambda x: x['amount'])
        tx_content['out'].sort(key= lambda x: x['amount'])
        input_values = [add['amount'] for add in tx_content['in']]
        output_values = [add['amount'] for add in tx_content['out']]
        if len(output_values) > 1:
            # We get the previous transaction, from which tx_content comes from. (So, from the previous layer)
            tx_index = find_transaction(self.transaction_lists[self.layer_counter - 1], txid)
            if tx_index == -1:
                print(f"Error, something went wrong. Selecting all inputs by default.")
                return tx_content['in']
            else:
                observed_addresses = self.transaction_lists[self.layer_counter - 1][tx_index].output_addresses
                observed_outputs = [add for add in tx_content['out'] if add in observed_addresses]

            # First check: input_values match with output_values AND that we have the same number of input/outputs
            if input_values == output_values:
                # Only ONE input value matches our output value(s) - there can be multiple output addresses to look at
                used_indexes = set()
                for add in observed_outputs:
                    if add['amount'] in input_values and output_values.index(add['amount'])not in used_indexes:
                        used_indexes.add(input_values.index(add['amount']))
                if len(used_indexes) == len(observed_addresses):  # If it's the case:
                    for i in used_indexes:
                        tx_content['in'][i]['special'] = True
                    return [tx_content['in'][i] for i in used_indexes]

            # Second check: there is a sublist of input values whose sum equals our output values (two by two)
            # - Again, there can be multiple output values to look at
            # TODO: Implement that part, complexity of !n so we need to find another way.
            # used_indexes = set()
            # all_good = True
            # for add in observed_outputs:
            #     indexes = sub_array_sum(input_values, add['value'])
            #     if indexes:
            #         in_set = False
            #         for index in indexes:
            #             if index in used_indexes:
            #                 all_good = False
            #                 break
            #         used_indexes.update(indexes)
            #     else:
            #         break
        if input_values[-1] / sum(input_values) > 0.95:  # If one input value represents more than 95% of the total
            tx_content['in'][-1]['special'] = True
            return [tx_content['in'][-1]]
        else:
            # We also want to prune tx if a number -let's say 20%- of tx represents more than 70% of the total
            nb_tx = math.ceil(len(input_values) * 0.2)
            if sum(input_values[-1 - nb_tx: -1]) / sum(input_values) > 0.70:
                return tx_content['in'][-1 - nb_tx: -1]
        return tx_content['in']

    def start_analysis(self):
        self.get_wallet_transactions()

        while self.layer_counter <= self.nb_layers:
            print(f"Layer counter: {self.layer_counter}")
            self.get_addresses_from_txid()

        print(f"\n\n\n--------- FINAL RESULTS ---------\n")
        for i in range(self.nb_layers + 1):
            print(f"Layer {i}: {len(self.transaction_lists[i])}")

        print("\n\n")
        for i in range(self.nb_layers + 1):
            print(f"Tx of layer {i}:")
            for tx in self.transaction_lists[i][:15]:
                print(tx)
            if len(self.transaction_lists[i]) >= 15:
                print("...")
            print("\n")

    def check_request_limit(self):
        """
        Checks if we can still make requests. If we can't, we wait until we can.
        :return:
        """
        if self.remaining_req == 0:
            waiting_bar(10)  # Sleeps 10 seconds
            self.remaining_req = 45

    def get_statistics(self):
        """
        Prints the number of pruned tx and identified tx per layer
        :return: None
        """
        print(f"\n\n\n--------- STATISTICS ---------\n")
        pruned_tx_lists = {}
        tagged_tx_lists = {}

        for layer in range(self.layer_counter):
            pruned_tx_lists[layer] = []
            tagged_tx_lists[layer] = []
            for tx in self.transaction_lists[layer]:
                if tx.tag:
                    tagged_tx_lists[layer].append(tx)
                if tx.is_special:
                    pruned_tx_lists[layer].append(tx)

        print(f"Number of tagged transactions by layer: \n" +
              "\n".join([f"Layer {layer}: {len(tagged_tx_lists[layer])} - {[tx.txid for tx in tagged_tx_lists[layer]]}"
                         for layer in range(self.layer_counter)]) + "\n")

        print(f"Number of pruned transactions by layer: \n" +
              "\n".join([f"Layer {layer}: {len(pruned_tx_lists[layer])}"
                         for layer in range(self.layer_counter)]) + "\n\n\n")

    # def read_proxy_list(self):
    #     with open("http_proxies.txt", "r") as f:
    #         for line in f.readlines():
    #             if line:
    #                 self.proxy_list.append(line.strip())
    #                 self.proxy_used.append(0)
    #
    # def change_session_proxy(self):
    #     proxy_found = False
    #     proxy = 0
    #     print("Changing proxy!")
    #     if 0 not in self.proxy_used:
    #         # If we have used every proxy (and potentially reached the req. limit on all of them)
    #         print(f"No more proxy available, please wait until they are refreshed...")
    #         waiting_bar(60)  # Wait for 60 seconds
    #         self.proxy_used = [0 for _ in range(len(self.proxy_list))]  # Reset the list of used proxies
    #
    #     while not proxy_found:  # Since there is at least one 0 in the list, we will find an available proxy
    #         proxy = random.randint(0, len(self.proxy_list) - 1)
    #         print(f"Trying Proxy {proxy}")
    #         if self.proxy_used[proxy] == 0:
    #             self.proxy_used[proxy] = 1
    #             proxy_found = True
    #
        # print("Proxy found!")
        # self.session.proxies = {
        #     'http': f"http://{self.proxy_list[proxy]}",  # 185.61.152.137:8080
        #     'https': f"https://{self.proxy_list[proxy]}",
        # }


def waiting_bar(seconds):
    """
    Loading bar waiting for "seconds" sec
    :param seconds: number of seconds to wait
    :return:
    """
    for _ in Bar('Waiting for request limit', suffix='%(percent)d%%').iter(range(1, seconds + 1)):
        time.sleep(1)


def sub_array_sum(arr, sum_):
    curr_sum = arr[0]
    start = 0

    i = 1
    while i <= len(arr):
        while curr_sum > sum_ and start < i - 1:
            curr_sum = curr_sum - arr[start]
            start += 1

        if curr_sum == sum_:
            return [k for k in range(start, i)]

        if i < len(arr):
            curr_sum = curr_sum + arr[i]
        i += 1

    return []