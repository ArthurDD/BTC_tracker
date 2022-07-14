import concurrent
import math
import random
from concurrent.futures import ThreadPoolExecutor, wait
import time
from datetime import timedelta
from functools import partial
# from requests.exceptions import HTTPError
import sys
# import requests
import requests_cache
from request_limit_reached import RequestLimitReached
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt

from transaction import Transaction, find_transaction
from web_scraper import Scraper


class ChainParser:
    # TODO: Once all the requests have been made to retrieve input addresses and their respective txid, check if the
    #  addresses have already been clustered. If they have, we stop and "identify" these BTC. If not, we go through
    #  another layer (until we reach our layer limit)
    #  We also need to check whether the coins have been mined or not (if so, identify BTC and stop)
    def __init__(self, address, nb_layers, rto_threshold=0.1, cache_expire=14):
        self.address = address
        self.root_value = 0
        self.nb_layers = nb_layers
        self.wallet_url = f"http://www.walletexplorer.com/api/1/address?address={address}" \
                          f"&from=0&count=100&caller=3"
        self.identified_btc = []
        self.transaction_lists = {i: [] for i in range(nb_layers + 1)}
        self.session = requests_cache.CachedSession('parser_cache_test',
                                                    use_cache_dir=True,  # Save files in the default user cache dir
                                                    cache_control=True,
                                                    # Use Cache-Control headers for expiration, if available
                                                    expire_after=timedelta(days=cache_expire),
                                                    # Otherwise expire responses after 14 days)
                                                    )
        self.layer_counter = 0
        self.remaining_req = 45  # Number of requests that we are allowed to make simultaneously
        self.added_before = []
        self.rto_threshold = rto_threshold  # rto_threshold is in percentage of the total address received amount

        self.web_scraper = Scraper(self.address, self.session)
        self.ba_reports = {i: [] for i in range(self.nb_layers + 1)}
        self.already_queried_addresses = set()

        self.time_stat_dict = {i: [] for i in range(nb_layers + 1)}

        print(self.wallet_url)

    def thread_pool(self, function, url_list, address_list=None):
        """
        :param address_list: List of list of output addresses that we need to request reports for from bitcoinabuse.com.
        :param function: Either self._get_input_addresses or self._retrieve_txids_from_wallet
        :param url_list: List of URLs to parse
        :return: None
        """
        print("Starting threads")
        with ThreadPoolExecutor(max_workers=40) as executor, \
                tqdm(total=len(url_list), desc=f"Retrieving transactions for the layer {self.layer_counter}") as p_bar:
            fn = partial(function, p_bar)
            finished = False
            nb_tries = 5
            while not finished:
                finished = True  # Set it to True by default
                futures = []
                for i in range(len(url_list)):
                    url = url_list[i]
                    if address_list:
                        output_addresses = address_list[i]
                    else:
                        output_addresses = []

                    futures.append(executor.submit(fn, (url, output_addresses)))
                    if url not in self.session.cache.urls:  # If the URL has not been cached before
                        # We will have to respect the request limit of 2req/sec
                        time.sleep(0.5)

                # Wait for the first exception to occur
                # p_bar.write(f"Allocating the tasks...")
                done, not_done = wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)

                p_bar.write(f"Length of Done: {len(done)}")
                p_bar.write(f"not_done: {len(not_done)}")
                successful_urls = []
                for future in done:  # The failed future has still finished, so we need to catch the exc. raised
                    try:
                        successful_urls.append(future.result())
                    except RequestLimitReached:
                        p_bar.write("LIMIT REACHED")
                        finished = False
                        pass
                    except Exception as err:
                        if nb_tries == 0:
                            raise err
                        else:
                            finished = False
                            nb_tries -= 1
                            p_bar.write(f"Requests failed. ({err})\n {nb_tries} tries left.")
                            pass
                        # print(f"Unexpected error. ({err})")

                p_bar.write(f"Length of successful URLs: {len(successful_urls)}")
                # If all the requests were successful or if we got an error that is not the RequestLimitReached,
                # we get out of the while loop
                if not finished:
                    p_bar.write("Error while making requests (Request limit exceeded). Retrying in 5s...")
                    # Remove all the successful requests
                    url_list = [url for url in url_list if url not in successful_urls]
                    p_bar.write(f"Length of url_list is now: {len(url_list)}")

                    # self.change_session_proxy()  # Change the proxy of the session (and potentially wait for 60s)
                    self.session.close()
                    waiting_bar(30)  # Waiting for the limit to fade
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
            # print(req.json())

            nb_tx = req.json()["txs_count"]
            nb_req = nb_tx // 100 if nb_tx % 100 == 0 else nb_tx // 100 + 1
            tot_url_list = [f"http://www.walletexplorer.com/api/1/address?address={self.address}"
                            f"&from={i * 100}&count=100&caller=paulo" for i in range(nb_req)]

            print(f"Length of url_list: {len(tot_url_list)}")
            self.thread_pool(self._retrieve_txids_from_wallet, tot_url_list)

            # Once everything is done, increase layer counter
            self.layer_counter += 1

            self.transaction_lists[0].sort(key=lambda x: x.amount, reverse=True)

            self.root_value = sum([tx.amount for tx in self.transaction_lists[0]])
            self.rto_threshold = self.root_value * (self.rto_threshold / 100)
            print(f"Root value: {self.root_value}")

            print(f"Length of layer 0: {len(self.transaction_lists[0])}")
            print(f"Size of layer 0: {sys.getsizeof(self.transaction_lists[0])}")
            print()

    def _retrieve_txids_from_wallet(self, p_bar, req_info):
        """
        Function called by get_wallet_transactions to get the transaction ids from the wallet in input.
        Stores everything in self.transaction_lists[0].
        :param p_bar: tqdm progress bar, to print without messing the bar display
        :param req_info: Tuple of url to make the request to, and the addresses to query from BA. (url, [ad1, ad2..])
        :return: None
        """
        t_0 = time.time()
        try:
            time.sleep(random.random())
            link = req_info[0]  # Don't need to request BA in this function as the only add is the root address
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
            p_bar.update(1)
            content = req.json()
            for tx in content['txs']:
                if tx["amount_received"] > 0 and tx["amount_sent"] == 0:
                    # If it is a received transaction and not a sent one, and if it's not a payment that he did
                    # re-using his address (change-address = input address)
                    self.transaction_lists[self.layer_counter].append(Transaction(tx['txid'],
                                                                                  output_addresses=[self.address],
                                                                                  amount=tx["amount_received"],
                                                                                  rto=tx["amount_received"]))
            self.time_stat_dict[self.layer_counter].append(time.time() - t_0)
            return link

    def get_addresses_from_txid(self):
        """
        Requests every tx page of the current layer (from txids stored in transaction_lists[i]) to get input addresses
        of that tx and their respective txid
        :return: None
        """
        print(f"\n\n\n--------- RETRIEVING ADDRESSES FROM TXID LAYER {self.layer_counter}---------\n")
        tot_url_list = [f"http://www.walletexplorer.com/api/1/tx?txid={tx.txid}&caller=paulo"
                        for tx in self.transaction_lists[self.layer_counter - 1] if not tx.is_below_rto_threshold]
        tot_address_list = [tx.output_addresses for tx in self.transaction_lists[self.layer_counter - 1]
                            if not tx.is_below_rto_threshold]
        # tot_address_list = list(set(address for address in [tx.output_addresses
        #                                                     for tx in self.transaction_lists[self.layer_counter - 1]
        #                                                     if not tx.is_below_rto_threshold]))
        # print(f"Tot_address_list: {tot_address_list}")
        print(f"Length of tot_address_list: {len(tot_address_list)}")
        print(f"Number of requests to make: {len(tot_url_list)}")

        self.thread_pool(self._get_input_addresses, tot_url_list, tot_address_list)

        print(f"\n\nAdded before: {self.added_before}\n\n")
        print(f"Tx of layer {self.layer_counter}:")
        for tx in self.transaction_lists[self.layer_counter][:15]:
            print(tx)
        print("...")
        self.layer_counter += 1

    def _get_input_addresses(self, p_bar, req_info):
        """
        Called by get_addresses_from_txid.
        Only used to parse the page at the indicated link. Retrieves BTC input address of a transaction as well as its
        associated txid.
        :param p_bar: tqdm progress bar, to print without messing the bar display
        :param req_info: Tuple of url to make the request to, and the addresses to query from BA. (url, [ad1, ad2..])
        :return:
        """
        t_0 = time.time()
        link = req_info[0]
        # print(f"Link: {link}")
        output_addresses = req_info[1]
        # print(f"Output_addresses: {output_addresses}\n\n")
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
            # We do bitcoinabuse requests:
            for add in output_addresses:
                # We first check that the address is not already in ba_reports
                time.sleep(random.random())  # Since requests are made (almost) simultaneously, sometimes they are not
                # added fast enough to the list, and are therefore queried multiple times
                # (only an issue for the first layer and when the tx requests have been cached)
                if add not in self.already_queried_addresses:
                    self.already_queried_addresses.add(add)
                    ba_info = self.web_scraper.bitcoinabuse_search(add)
                    if ba_info:
                        # p_bar.write(f"ba_reports: {self.ba_reports[self.layer_counter - 1]}")
                        self.ba_reports[self.layer_counter - 1].append(ba_info)
            p_bar.update(1)
            tx_content = req.json()
            txid = link[link.find("txid="):].split("&")[0][5:]
            # print(tx_content)
            if tx_content["is_coinbase"]:  # If it's mined bitcoins
                # print(f"MINED BITCOINS")
                i = find_transaction(self.transaction_lists[self.layer_counter - 1], txid)
                self.transaction_lists[self.layer_counter - 1][i].tag = "Mined"
            elif "label" in tx_content:  # If the input address has been identified, we add the tag to the tx
                # print(f"IDENTIFIED BITCOIN")
                i = find_transaction(self.transaction_lists[self.layer_counter - 1], txid)
                self.transaction_lists[self.layer_counter - 1][i].tag = tx_content['label']
                # We don't need to go through the inputs of this tx as we've already found out where the BTC are from.
            else:
                # print(f"Number of inputs before pruning: {len(tx_content['in'])}")
                # We select the inputs that we want to keep
                selected_inputs = self.select_inputs(tx_content, txid)

                for add in selected_inputs:
                    if add['is_standard']:  # To manage the case with OPCODE (see notes)
                        i = find_transaction(self.transaction_lists[self.layer_counter], add["next_tx"])
                        if i == -1:  # Means we have not added that txid to the next layer yet
                            self.transaction_lists[self.layer_counter].append(
                                Transaction(txid=add['next_tx'], prev_txid=txid,
                                            amount=add['amount'],
                                            rto=add['rto'],
                                            output_addresses=[add['address']],
                                            is_pruned=add['pruned'] if 'pruned' in add else None,   # Not used anymore
                                            rto_threshold=self.rto_threshold))
                        else:
                            self.added_before.append(add['next_tx'])
                            # print("ADDED BEFORE")
                            self.transaction_lists[self.layer_counter][i].amount += add['amount']
                            if add['address'] not in self.transaction_lists[self.layer_counter][i].output_addresses:
                                self.transaction_lists[self.layer_counter][i].output_addresses.append(add['address'])
            self.time_stat_dict[self.layer_counter].append(time.time() - t_0)
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
        tx_content['out'].sort(key=lambda x: x['amount'])
        input_values = [add['amount'] for add in tx_content['in']]
        output_values = [add['amount'] for add in tx_content['out']]

        # We get the previous transaction, from which tx_content comes from. (So, from the previous layer)
        # This transaction is unique.
        tx_index = find_transaction(self.transaction_lists[self.layer_counter - 1], txid)
        if tx_index == -1:  # This case should never happen
            print(f"Error, something went wrong. Selecting all inputs by default.")
            self.set_rto(tx_content['in'], -1)
            return tx_content['in']
        else:
            observed_addresses = self.transaction_lists[self.layer_counter - 1][tx_index].output_addresses
            observed_rto = self.transaction_lists[self.layer_counter - 1][tx_index].rto
            observed_outputs = [add for add in tx_content['out'] if add in observed_addresses]

        if len(input_values) > 1:
            # First, we calculate the tx fee by adding all the input values and subtracting the output values
            tx_fee = sum(input_values) - sum(output_values)
            # print(f"tx_fee for {txid}: {tx_fee}")
            # Then, 1st check: input_values match with output_values AND that we have the same number of input/outputs
            for i in range(len(output_values)):
                output_values[i] += tx_fee
                if input_values == output_values:
                    # Only ONE input value matches our output value(s) (two by two)
                    # - there can be multiple output addresses to look at
                    used_indexes = set()
                    for add in observed_outputs:
                        if add['amount'] in input_values and output_values.index(add['amount']) not in used_indexes:
                            used_indexes.add(input_values.index(add['amount']))
                    if len(used_indexes) == len(observed_addresses):  # If it's the case:
                        selected_inputs = [tx_content['in'][i] for i in used_indexes]
                        print(f"FACULTY")
                        # self.transaction_lists[self.layer_counter - 1][tx_index].is_pruned = True
                    else:
                        selected_inputs = tx_content['in']

                    return selected_inputs

            # Second check: there is a sublist of input values whose sum equals our output values (two by two)
            # - Again, there can be multiple output values to look at
            # TODO: Implement that part, complexity of n! so we need to find another way.

            if input_values[-1] / sum(input_values) > 0.95:  # If one input value represents more than 95% of the tot.
                selected_inputs = [tx_content['in'][-1]]

            else:
                # We also want to prune tx if a number -let's say 20%- of tx represents more than 80% of the total
                nb_tx = math.ceil(len(input_values) * 0.2)
                if sum(input_values[-1 - nb_tx:]) / sum(input_values) > 0.80:
                    selected_inputs = tx_content['in'][-1 - nb_tx:]

                elif len(input_values) > 50:  # If too many transactions, we prune them and only take the 10 biggest
                    selected_inputs = tx_content['in'][-1 - 10:]
                else:
                    selected_inputs = tx_content['in']

        else:
            # Need to add the rto to the only input transaction (= to previous rto)
            selected_inputs = tx_content['in']

        if len(selected_inputs) != len(tx_content['in']):
            self.transaction_lists[self.layer_counter - 1][tx_index].is_pruned = True

        self.set_rto(selected_inputs, observed_rto)  # We set the RTO to all the selected transactions

        return selected_inputs

    def set_rto(self, input_list, rto):
        """
        Set rto to each of the tx that are in input_list according to their value
        :param input_list: Dict of the inputs of a transaction (i.e. future transactions in the next layer)
        :param rto: rto of the current transaction to share between the next transactions
        :return: None
        """
        sum_value = sum([float(tx['amount']) for tx in input_list])
        # print(f"\n\nSum value: {sum_value}")
        # print(f"Previous RTO: {rto}")

        for i in range(len(input_list) - 1, -1, -1):
            # print(f"Amount of the input: {input_list[i]['amount']}")
            input_list[i]['rto'] = (float(input_list[i]['amount']) / sum_value) * rto

            # We only keep transactions with RTOs > threshold
            if input_list[i]['rto'] < self.rto_threshold:
                input_list.pop(i)

    def already_queried(self, address):
        """
        Returns whether the address has already been queried on BitcoinAbuse or not.
        :param address: address to look
        :return: Bool -> False if not queried yet, True if already in the report list.
        """
        for elt in self.ba_reports[self.layer_counter - 1]:
            if elt['address'] == address:
                return True
        return False

    def clean_reports(self):
        """
        Removes reports that are in the same layer more than once (happens because the requests are made too fast
        for the function to not make the request if the address is already in the list)
        Also removes empty reports (i.e. found = False)
        :return: None
        """
        for i in range(self.nb_layers + 1):
            self.ba_reports[i] = list(filter(lambda elt: elt['found'] is True, self.ba_reports[i]))

    def start_analysis(self):
        """ Method to start the analysis of the root address. Builds every layer. """
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

        print("\n\n")
        self.clean_reports()  # Removes empty reports
        print(f"Cleaned BA_reports: {self.ba_reports}\n\n")

        print(f"RTO threshold is: {self.rto_threshold}")

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
        Main function to display stats.
        - Prints the number of pruned tx and identified tx per layer.
        - Calls methods to display other stats/charts
        :return: None
        """
        print(f"\n\n\n--------- STATISTICS ---------\n")
        pruned_tx_lists = {}
        tagged_tx_lists = {}
        tagged_tx_rto = {}

        for layer in range(self.layer_counter):
            pruned_tx_lists[layer] = []
            tagged_tx_lists[layer] = []
            tagged_tx_rto[layer] = 0
            for tx in self.transaction_lists[layer]:
                if tx.tag:
                    tagged_tx_lists[layer].append(tx)
                    tagged_tx_rto[layer] += tx.rto
                if tx.is_pruned:
                    pruned_tx_lists[layer].append(tx)

        print(f"Number of tagged transactions by layer: \n" +
              "\n".join([f"Layer {layer}: {len(tagged_tx_lists[layer])} - {[tx.txid for tx in tagged_tx_lists[layer]]}"
                         for layer in range(self.layer_counter)]) + "\n")

        print(f"Number of pruned transactions by layer: \n" +
              "\n".join([f"Layer {layer}: {len(pruned_tx_lists[layer])}"
                         for layer in range(self.layer_counter)]) + "\n\n\n")

        print(f"Tagged transactions represent: {round(sum(tagged_tx_rto.values()), 4)} of the total amount of BTC. "
              f"({round(sum(tagged_tx_rto.values()) / self.root_value * 100, 2)}% of the total)")

        self.display_tagged_stats(tagged_tx_lists, tagged_tx_rto)

    def display_time_stats(self, ax=None):
        """
        Displays the average request time per layer
        :param ax: If set to none, displays the bar chart on its own plot. If not, builds the chart on ax directly
        :return: None
        """
        display = False
        if not ax:
            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1)
            display = True

        layers = [f"L-{i} ({len(self.time_stat_dict[i])} req.)" for i in range(self.nb_layers + 1)]
        x_pos = np.arange(0, len(layers))
        avg_time = [np.mean(time_l) for time_l in self.time_stat_dict.values()]

        ax.bar(x_pos, avg_time, align='center', width=0.5)
        ax.set_xlabel('Layers')
        ax.set_ylabel('Time (s)')
        ax.set_title('Average request time per layer')

        if display:
            plt.show()

    def display_tagged_stats(self, tagged_tx_lists, tagged_tx_rto):
        """
        Displays 2 graphs: one with how many transactions were tagged per layer, and one with rto information
        :return: None
        """
        figure, axis = plt.subplots(2, 2)

        tagged_by_layer = [len(tx_list) for tx_list in tagged_tx_lists.values()]
        layers = [i for i in range(len(tagged_by_layer))]

        sum_rto_by_layer = [sum(list(tagged_tx_rto.values())[:i + 1]) for i in range(len(tagged_tx_rto))]

        axis[0, 0].bar(layers, tagged_by_layer, color='blue')
        axis[0, 0].set_ylabel("Tagged tx")
        axis[0, 0].set_xlabel("Layers")
        axis[0, 0].set_title("Tagged transactions by layer")

        axis[0, 1].bar(layers, tagged_tx_rto.values(), color='orange')
        axis[0, 1].set_ylabel("RTO")
        axis[0, 1].set_xlabel("Layers")
        axis[0, 1].set_title("Sum of tagged tx's RTO by layer")

        ax_twin = axis[0, 1].twinx()
        ax_twin.plot(layers, sum_rto_by_layer, color='green')
        ax_twin.set_ylabel("Total (BTC)")

        self.display_time_stats(axis[1, 0])

        # plt.subplots_adjust(wspace=0.3, hspace=0.3)

        # plt.show()
        plt.tight_layout()
        plt.show()


def waiting_bar(seconds):
    """
    Loading bar waiting for "seconds" sec
    :param seconds: number of seconds to wait
    :return:
    """
    for _ in tqdm(range(seconds)):
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
