import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import timedelta
from functools import partial
import sys
import requests_cache

from graph_visualisation import GraphVisualisation
from request_limit_reached import RequestLimitReached
from tqdm import tqdm
import numpy as np

import matplotlib
import matplotlib.pyplot as plt

from transaction import Transaction, find_transaction
from web_scraper import Scraper

FILE_DIR = os.path.dirname(os.path.abspath(__file__))  # PATH to BTC_tracker


class ChainParser:
    def __init__(self, address, nb_layers, rto_threshold=0.1, cache_expire=14, send_fct=None):
        self.address = address
        self.root_value = 0
        self.nb_layers = nb_layers
        self.wallet_url = f"http://www.walletexplorer.com/api/1/address?address={address}" \
                          f"&from=0&count=100&caller=3"
        self.transaction_lists = {i: [] for i in range(nb_layers + 1)}
        self.session = requests_cache.CachedSession('parser_cache',
                                                    # use_cache_dir=True,  # Save files in the default user cache dir
                                                    cache_control=True,
                                                    # Use Cache-Control headers for expiration, if available
                                                    expire_after=timedelta(days=cache_expire),
                                                    # Otherwise expire responses after 14 days)
                                                    )
        print("PAAAAAAATTTTHHHHH: ", self.session.cache.db_path)
        self.layer_counter = 0
        self.remaining_req = 45  # Number of requests that we are allowed to make simultaneously
        self.added_before = []
        self.rto_threshold = rto_threshold  # here, rto_threshold is in percentage of the total address received amount
        self.input_addresses = dict()

        self.web_scraper = Scraper(self.address, self.session)
        self.ba_reports = {i: [] for i in range(self.nb_layers + 1)}
        self.already_queried_addresses = set()

        self.time_stat_dict = {key: {j: [] for j in range(nb_layers + 1)} for key in
                               ['request', 'find_tx', 'select_input', 'adding_addresses', 'overall']}
        self.analysis_time = 0

        self.send_fct = send_fct  # Takes 2 arg = message to send to the socket and message_type (optional)

        print(self.wallet_url)

    def thread_pool(self, function, url_list):
        """
        :param function: Either self._get_input_addresses or self._retrieve_txids_from_wallet
        :param url_list: List of URLs to parse
        :return: None
        """
        sec_to_wait = 25
        print("Starting threads...")
        if self.send_fct is not None:
            message = '{' + f'"layer": {self.layer_counter}, "total": "{len(url_list)}"' + '}'
            self.send_fct(message=message, message_type='progress_bar_start')

        cached_urls = []
        for i in range(len(url_list) - 1, -1, -1):
            url = url_list[i]
            if url in self.session.cache.urls:
                cached_urls.append(url)
                url_list.pop(i)
        print(f"Length of cached urls: {len(cached_urls)}")
        print(f"Length of not-cached urls: {len(url_list)}")
        with tqdm(total=len(url_list) + len(cached_urls),
                  desc=f"Retrieving transactions for the layer {self.layer_counter}") as p_bar:
            fn = partial(function, p_bar)

            if cached_urls:
                with ThreadPoolExecutor(max_workers=40) as executor:
                    # Makes requests if they are already cached (bc we don't have any rate limit)
                    executor.map(fn, cached_urls)
                    # Wait for the futures to be finished

            # Requests that have not been cached
            finished = False
            nb_tries = 5
            req_counter = 0
            pause_required = False
            if url_list:
                while not finished:
                    try:
                        url = url_list[req_counter]
                        fn(url)
                    except RequestLimitReached:
                        if nb_tries == 0:
                            if self.send_fct is not None:
                                self.send_fct(message="Error while making requests. Number of tries exceeded."
                                                      " Please start the parsing again.")
                            raise err
                        else:
                            nb_tries -= 1
                            reason = "Request Limit reached"
                            pause_required = True
                        pass
                    except Exception as err:
                        if nb_tries == 0:
                            if self.send_fct is not None:
                                self.send_fct(message="Error while making requests. Number of tries exceeded."
                                                      " Please start the parsing again.")
                            raise err
                        else:
                            nb_tries -= 1
                            # p_bar.write(f"Requests failed. ({err})\n {nb_tries} tries left.")
                            reason = str(err)
                            pause_required = True

                    if pause_required:  # If the request did not go through, we pause
                        p_bar.write(f"Error while making requests ({reason}). Retrying in 25s... "
                                    f"({nb_tries} attempts left)")
                        if self.send_fct is not None:
                            self.send_fct(f"Error while making requests ({reason}). Retrying in {sec_to_wait}sec... "
                                          f"({nb_tries} attempt(s) left)")
                            self.send_fct(sec_to_wait, message_type='waiting_bar')

                        self.session.close()
                        waiting_bar(sec_to_wait)  # Waiting for the limit to fade
                        self.session = requests_cache.CachedSession('parser_cache')
                    else:  # Otherwise, if it did go through, it means we can go to the next request
                        req_counter += 1
                        if req_counter == len(url_list):  # End condition
                            finished = True
                        else:
                            time.sleep(0.6)  # Limited by the API to 2 req/sec

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
            content = req.json()
            if 'txs_count' not in content:
                if self.send_fct is not None:
                    self.send_fct("Error, this address doesn't seem to exist.", message_type='error')
                else:
                    print(f"Error, this address doesn't seem to exist.")
                return False

            nb_tx = req.json()["txs_count"]
            if nb_tx == "0":
                if self.send_fct is not None:
                    self.send_fct("Error, this address has not made any transaction yet.", message_type='error')
                else:
                    print(f"Error, this address doesn't seem to exist.")
                return False
            nb_req = nb_tx // 100 if nb_tx % 100 == 0 else nb_tx // 100 + 1
            tot_url_list = [f"https://www.walletexplorer.com/api/1/address?address={self.address}"
                            f"&from={i * 100}&count=100&caller=paulo" for i in range(nb_req)]

            print(f"Length of url_list: {len(tot_url_list)}")
            self.thread_pool(self._retrieve_txids_from_wallet, tot_url_list)

            # Once everything is done, increase layer counter
            self.layer_counter += 1

            self.transaction_lists[0].sort(key=lambda x: x.amount, reverse=True)  # Ordering tx acc. to their amount

            # Initializing values
            self.root_value = sum([tx.amount for tx in self.transaction_lists[0]])
            self.rto_threshold = self.root_value * (self.rto_threshold / 100)

            # Need to remove the tx from layer 0 whose RTO is too low
            for i, tx in reversed(list(enumerate(self.transaction_lists[0]))):
                if tx.rto < self.rto_threshold:
                    # print(f"Tx {tx.txid}'s RTO is too low! ({tx.rto} RTO)")
                    self.transaction_lists[0].pop(i)
            print(f"Root value: {self.root_value}")

            print(f"Length of layer 0: {len(self.transaction_lists[0])}")
            print(f"Size of layer 0: {sys.getsizeof(self.transaction_lists[0])}")
            print()
            return True

    def _retrieve_txids_from_wallet(self, p_bar, link):
        """
        Function called by get_wallet_transactions to get the transaction ids from the wallet in input.
        Stores everything in self.transaction_lists[0].
        :param p_bar: tqdm progress bar, to print without messing the bar display
        :param link: url to make the request to
        :return: None
        """
        t_0 = time.time()
        try:
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
            if self.send_fct is not None:
                self.send_fct(1, message_type="progress_bar_update")
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
            self.time_stat_dict['request'][self.layer_counter].append(time.time() - t_0)
            return link

    def get_addresses_from_txid(self):
        """
        Requests every tx page of the current layer (from txids stored in transaction_lists[i]) to get input addresses
        of that tx and their respective txid
        :return: None
        """
        print(f"\n\n\n--------- RETRIEVING ADDRESSES FROM TXID LAYER {self.layer_counter}---------\n")
        tot_url_list = [f"https://www.walletexplorer.com/api/1/tx?txid={tx.txid}&caller=paulo"
                        for tx in self.transaction_lists[self.layer_counter - 1] if not tx.is_manually_deleted]
        tot_address_list = [tx.output_addresses for tx in self.transaction_lists[self.layer_counter - 1]]

        print(f"Length of tot_address_list: {len(tot_address_list)}")

        self.thread_pool(self._get_input_addresses, tot_url_list)

        print(f"\n\nTransactions added before: {self.added_before}\n\n")
        # print(f"Tx of layer {self.layer_counter}:")
        # for tx in self.transaction_lists[self.layer_counter][:15]:
        #     print(tx)
        # print("...")
        self.layer_counter += 1

    def _get_input_addresses(self, p_bar, link):
        """
        Called by get_addresses_from_txid.
        Only used to parse the page at the indicated link. Retrieves BTC input address of a transaction as well as its
        associated txid.
        :param p_bar: tqdm progress bar, to print without messing the bar display
        :param link: Url to make the request to
        :return:
        """
        t_0 = time.time()

        try:
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
            t_request = time.time()
            if self.send_fct is not None:
                self.send_fct(1, message_type="progress_bar_update")
            p_bar.update(1)
            tx_content = req.json()
            txid = link[link.find("txid="):].split("&")[0][5:]
            if tx_content["is_coinbase"]:  # If it's mined bitcoins
                i = find_transaction(self.transaction_lists, txid, layer=self.layer_counter - 1)
                self.transaction_lists[self.layer_counter - 1][i].tag = "Mined"
            elif "label" in tx_content:  # If the input address has been identified, we add the tag
                # to the tx it comes from
                i = find_transaction(self.transaction_lists, txid, layer=self.layer_counter - 1)
                self.transaction_lists[self.layer_counter - 1][i].tag = tx_content['label']
                # We don't need to go through the inputs of this tx as we've already found out where the BTC are from.
            else:
                # print(f"Number of inputs before pruning: {len(tx_content['in'])}")
                # We select the inputs that we want to keep
                t_input = time.time()
                selected_inputs = self.select_inputs(tx_content, txid)

                t_adding = time.time()
                t_tx = []
                for add in selected_inputs:
                    if add['is_standard']:  # To manage the case with OPCODE (see notes)
                        t_0_tx = time.time()
                        pot_layer, i = find_transaction(self.transaction_lists, add["next_tx"])
                        t_tx.append(time.time() - t_0_tx)
                        if i == -1:  # Means we have not added that txid to the next layer yet
                            self.transaction_lists[self.layer_counter].append(
                                Transaction(txid=add['next_tx'], prev_txid=[(txid, self.layer_counter - 1)],
                                            amount=add['amount'],
                                            rto=add['rto'],
                                            output_addresses=[add['address']]))

                        else:
                            self.added_before.append(add['next_tx'])
                            # print("ADDED BEFORE")
                            if add['address'] not in self.transaction_lists[pot_layer][i].output_addresses:
                                # If the address is already in the list, it means that we ended up on a loop
                                self.transaction_lists[pot_layer][i].amount += add['amount']
                                self.transaction_lists[pot_layer][i].prev_txid.append((txid, self.layer_counter - 1))
                                self.transaction_lists[pot_layer][i].output_addresses.append(add['address'])
                                self.transaction_lists[pot_layer][i].rto += add['rto']

                t_tx_avg = np.mean(t_tx) if t_tx else 0
                self.time_stat_dict['request'][self.layer_counter].append(t_request - t_0)
                self.time_stat_dict['select_input'][self.layer_counter].append(t_adding - t_input)
                self.time_stat_dict['adding_addresses'][self.layer_counter].append(time.time() - t_adding)
                self.time_stat_dict['find_tx'][self.layer_counter].append(t_tx_avg)
            self.time_stat_dict['overall'][self.layer_counter].append(time.time() - t_0)
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
        tx_index = find_transaction(self.transaction_lists, txid, layer=self.layer_counter - 1)
        if tx_index == -1:  # This case should never happen in theory
            print(f"Error, something went wrong. Selecting all inputs by default.")
            self.set_rto(tx_content['in'], -1)
            return tx_content['in']
        else:
            observed_addresses = self.transaction_lists[self.layer_counter - 1][tx_index].output_addresses
            observed_rto = self.transaction_lists[self.layer_counter - 1][tx_index].rto
            observed_outputs = [add for add in tx_content['out'] if add['address'] in observed_addresses]

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
                        print(f"FINALLY")
                        # self.transaction_lists[self.layer_counter - 1][tx_index].is_pruned = True
                    else:
                        selected_inputs = tx_content['in']

                    self.set_rto(selected_inputs, observed_rto)  # We set the RTO to all the selected transactions
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
        # and remove low ones

        return selected_inputs

    def set_rto(self, input_list, rto):
        """
        Set rto to each of the tx that are in input_list according to their value
        :param input_list: Dict of the inputs of a transaction (i.e. future transactions in the next layer)
        :param rto: rto of the current transaction to share between the next transactions
        :return: None
        """
        sum_value = sum([float(tx['amount']) for tx in input_list])

        for i in range(len(input_list) - 1, -1, -1):
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
        for elt in self.ba_reports[self.layer_counter]:  # - 1]:
            if elt['address'] == address:
                return True
        return False

    def make_ba_request(self, add):
        # We first check that the address is not already in ba_reports
        if add not in self.already_queried_addresses:
            self.already_queried_addresses.add(add)
            ba_info = self.web_scraper.bitcoinabuse_search(add)
            if ba_info:
                self.ba_reports[self.layer_counter].append(ba_info)  # removed - 1 from self.layer_counter

    def clean_reports(self):
        """
        Removes reports that are in the same layer more than once (happens because the requests are made too fast
        for the function to not make the request if the address is already in the list)
        Also removes empty reports (i.e. found = False)
        :return: None
        """
        for i in range(self.nb_layers + 1):
            self.ba_reports[i] = list(filter(lambda elt: elt['found'] is True, self.ba_reports[i]))

    def set_reported_addresses(self):
        for layer in range(self.nb_layers + 1):
            for report in self.ba_reports[layer]:
                if report['genuine_recent_count'] > 0:
                    add = report['address']
                    # Find all the transactions that have add in output_add and tag them

    def start_analysis(self, manual=False, tx_to_remove=None, display_partial_graph=False):
        """ Method to start the analysis of the root address. Builds every layer.
        If manual is set to True, start_analysis is going to build every layer but one at a time,
        stopping at every layer. If self.layer_counter > self.nb_layers, display final stats
        :param display_partial_graph: Bool to display or not the graph in between each layer
        :param tx_to_remove: List of tx indexes to remove in case of a manual parsing
        :param manual: Enables/Disables manual parsing
        :return True if layer analysis didn't encounter any error, False otherwise"""

        t_0 = time.time()
        if tx_to_remove is not None:
            for i in tx_to_remove:  # Go through all the tx indices to stop the parsing with
                self.transaction_lists[self.layer_counter - 1][i].is_manually_deleted = True

        if self.layer_counter == 0:
            result = self.get_wallet_transactions()  # Counter gets increased in that method
            if result:
                if manual:
                    self.select_transactions()
                    # At that point, layer 0 has been parsed and manually pruned and layer_counter is 1
                    if display_partial_graph:  # To display the layer 0 graph
                        self.display_partial_graph()
                    self.analysis_time += time.time() - t_0
                    return result  # Not sure we use this output
        else:
            result = True

        if display_partial_graph:  # To display the layer 0 graph
            self.display_partial_graph()

        if result and not manual:  # Only if layer 0 has been successful and we are not in manual mode
            while self.layer_counter <= self.nb_layers:  # Go through all the layers
                print(f"Layer counter: {self.layer_counter}")
                self.get_addresses_from_txid()  # counter gets increased in that method

                if self.send_fct is not None:
                    self.send_fct(f"Layer {self.layer_counter - 1} done!")

                if display_partial_graph and self.layer_counter <= self.nb_layers:
                    # To display the layer self.lay_counter graph only if this is not the last layer
                    self.display_partial_graph()
            self.analysis_time += time.time() - t_0
            self.print_final_results()

            return True

        elif result and manual:  # If it's not layer 0 and we are in manual mode
            if self.layer_counter <= self.nb_layers:  # If there is still a layer to parse
                self.get_addresses_from_txid()  # counter gets increased in that method

                if self.send_fct is not None:
                    self.send_fct(f"Layer {self.layer_counter - 1} done!")

                self.select_transactions()

                if display_partial_graph and self.layer_counter <= self.nb_layers:
                    # To display the layer self.lay_counter graph only if this is not the last layer
                    self.display_partial_graph()
            else:  # If everything is parsed, we print final results
                self.print_final_results()
            self.analysis_time += time.time() - t_0
            return True  # Not sure we use this output

        return False

    def display_partial_graph(self):
        """
        Called by start_analysis method to display partial graph once each layer is done
        :return:
        """
        tree = GraphVisualisation(self.transaction_lists, until=self.layer_counter)
        file_name = tree.build_tree()

        print(f"File_name is: {file_name}")
        if file_name != "":
            self.send_fct(message=file_name, message_type='partial_svg_file')
        time.sleep(1.5)

    def select_transactions(self):
        """
        Select transactions to delete (=stop the parsing with) in case manual analysis is made.
        Sets is_manually_deleted to True if tx is deleted
        :return: None
        """
        layer = self.layer_counter - 1
        if self.send_fct is not None:  # In case program is running via UI
            data_tx = {'transactions': [{'index': i, 'txid': tx.txid, "amount": tx.amount,
                                         "rto": tx.rto, "rto_pt": np.round(tx.rto / self.root_value * 100, 2)}
                                        for i, tx in enumerate(self.transaction_lists[layer])],
                       'layer': layer}

            self.send_fct(message=str(json.dumps(data_tx)), message_type="manual_tx")

        else:  # In case we are running the program in the terminal
            print(f"Transactions found for that layer: ")
            for i, tx in enumerate(self.transaction_lists[layer]):
                print(f"{i}: {tx.txid}\nAmount: {tx.amount}BTC\nRTO: {tx.rto} BTC\n")
            tx_to_del = input("Please indicate the index of transactions to prune (separated by a comma):\n")
            if tx_to_del != "":
                tx_to_del = [int(elt) for elt in tx_to_del.split(',')]
            else:
                tx_to_del = []

            print(f"tx_to_del: {tx_to_del}")
            for i in tx_to_del:  # Go through all the tx indices to stop the parsing with
                self.transaction_lists[layer][i].is_manually_deleted = True

    def check_request_limit(self):
        """
        Checks if we can still make requests. If we can't, we wait until we can.
        :return:
        """
        if self.remaining_req == 0:
            waiting_bar(10)  # Sleeps 10 seconds
            self.remaining_req = 45

    def print_final_results(self):
        print(f"\n\n\n--------- FINAL RESULTS ---------\n")
        parsing_information = {"layer_info": {}, "total_txs": 0}
        for i in range(self.nb_layers + 1):
            parsing_information["layer_info"][i] = f"Layer {i}: {len(self.transaction_lists[i])}"
            parsing_information["total_txs"] += len(self.transaction_lists[i])
            print(f"Layer {i}: {len(self.transaction_lists[i])}")

        print(f"RTO threshold is: {self.rto_threshold}")
        parsing_information["rto_threshold"] = self.rto_threshold
        parsing_information["total_time"] = self.analysis_time

        if self.send_fct is not None:
            self.send_fct(message=str(json.dumps(parsing_information)), message_type='final_stats')
        print("\n\n")

    def get_statistics(self, display=False):
        """
        Main function to display stats.
        - Prints the number of pruned tx and identified tx per layer.
        - Calls methods to display other stats/charts
        :param display: Bool to display or not the plots.
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

        # print(f"Number of tagged transactions by layer: \n" +
        #       "\n".join([f"Layer {layer}: {len(tagged_tx_lists[layer])} - {[tx.txid for tx in tagged_tx_lists[layer]]}"
        #                  for layer in range(self.layer_counter)]) + "\n")
        #
        # print(f"Number of pruned transactions by layer: \n" +
        #       "\n".join([f"Layer {layer}: {len(pruned_tx_lists[layer])}"
        #                  for layer in range(self.layer_counter)]) + "\n\n\n")
        #
        # print(f"Tagged transactions represent: {round(sum(tagged_tx_rto.values()), 4)} of the total amount of BTC. "
        #       f"({round(sum(tagged_tx_rto.values()) / self.root_value * 100, 2)}% of the total)")
        print(f"Display is: {display}")
        self.display_tagged_stats(tagged_tx_lists, tagged_tx_rto, display=display)

    def display_time_stats(self, axes=None):
        """
        Displays the average request time per layer
        :param axes: If set to none, displays the bar chart on its own plot. If not, builds the chart on axes directly
        :return: None
        """
        display = False
        if not axes:
            fig = plt.figure()
            axes = fig.add_subplot(1, 1, 1)
            display = True

        # Request time
        ax_request = axes
        layers = [f"L-{i} ({len(self.time_stat_dict['request'][i])} req.)" for i in range(self.nb_layers + 1)]
        x_pos = np.arange(0, len(layers))
        request_avg_time = [np.mean(time_l) for time_l in self.time_stat_dict['request'].values()]
        select_input_avg_time = [np.mean(time_input) if time_input != [] else 0 for time_input in
                                 self.time_stat_dict['select_input'].values()]
        find_tx_avg_time = [np.mean(time_input) if time_input != [] else 0 for time_input in
                            self.time_stat_dict['find_tx'].values()]
        adding_addresses_avg_time = [np.mean(time_input) if time_input != [] else 0 for time_input in
                                     self.time_stat_dict['adding_addresses'].values()]
        overall_avg_time = [np.mean(time_input) if time_input != [] else 0 for time_input in
                            self.time_stat_dict['overall'].values()]

        print(f"Request_avg_time: {request_avg_time}")
        print(f"select_input_avg_time: {select_input_avg_time}")
        print(f"find_tx_avg_time: {find_tx_avg_time}")
        print(f"adding_addresses_avg_time: {adding_addresses_avg_time}")
        print(f"overall_avg_time: {overall_avg_time}")

        ax_request.bar(x_pos, request_avg_time, align='center', width=0.4, label="Avg. Request")
        ax_request.bar(x_pos, select_input_avg_time, align='center', width=0.4, label="Avg. Input Sel.")
        ax_request.set_xlabel('Layers', fontsize=18)
        ax_request.set_ylabel('Time (s)', fontsize=18)
        ax_request.set_title('Average function time per layer')
        ax_request.legend(loc='best')

        plt.savefig(FILE_DIR + '/doctest-output/plots/avg_function_time.png')
        if display:
            plt.show()

    def display_tagged_stats(self, tagged_tx_lists, tagged_tx_rto, display=False):
        """
        Displays 2 graphs: one with how many transactions were tagged per layer, and one with rto information
        :return: None
        """
        if not display:
            matplotlib.use('Agg')  # Change the library used to compute graphs. Agg works for backend only

        plt.style.use('seaborn')
        plt.clf()

        transactions_by_layer = [len(transaction_list) for transaction_list in self.transaction_lists.values()]
        layers = [i for i in range(len(transactions_by_layer))]
        plt.bar(layers, transactions_by_layer, color='green', width=0.4)
        for i in range(len(layers)):
            plt.text(i, transactions_by_layer[i], transactions_by_layer[i], ha='center')

        plt.ylabel("Number of tx", fontsize=18)
        plt.xlabel("Layers", fontsize=18)
        plt.title("Number of transactions by layer")

        plt.tight_layout()
        plt.savefig(FILE_DIR + '/doctest-output/plots/transactions_by_layer.png')

        if display:
            plt.show()

        plt.clf()
        tagged_by_layer = [len(tx_list) for tx_list in tagged_tx_lists.values()]
        layers = [i for i in range(len(tagged_by_layer))]

        plt.bar(layers, tagged_by_layer, width=0.4)
        for i in range(len(layers)):
            plt.text(i, tagged_by_layer[i], tagged_by_layer[i], ha='center')

        plt.ylabel("Tagged tx", fontsize=18)
        plt.xlabel("Layers", fontsize=18)
        plt.title("Tagged transactions by layer")

        plt.tight_layout()
        plt.savefig(FILE_DIR + '/doctest-output/plots/tagged_transactions_by_layer.png')

        if display:
            plt.show()

        plt.clf()
        sum_rto_by_layer = [sum(list(tagged_tx_rto.values())[:i + 1]) for i in range(len(tagged_tx_rto))]
        print(f"Tagged_tx_rto.values: {tagged_tx_rto.values()}")

        plt.bar(layers, tagged_tx_rto.values(), color='orange', width=0.4)
        plt.ylabel("RTO tagged by layer", fontsize=18)
        plt.xlabel("Layers", fontsize=18)
        plt.title("Sum of tagged tx's RTO by layer")

        sum_rto_by_layer = [sum(list(tagged_tx_rto.values())[:i + 1]) for i in range(len(tagged_tx_rto))]
        # print(f"sum_rto_by_layer: {sum_rto_by_layer}")
        ax_twin = plt.twinx()
        ax_twin.plot(layers, sum_rto_by_layer, color='green')
        ax_twin.yaxis.grid(False)  # Remove the horizontal lines for the second y_axis
        ax_twin.set_ylabel("Total (BTC)", fontsize=18)

        plt.tight_layout()
        plt.savefig(FILE_DIR + '/doctest-output/plots/tagged_tx_rto.png')

        if display:
            plt.show()

        print(f"Almost at the end")
        self.display_time_stats()

        # plt.show()

    def find_transactions(self):
        print(f"Finding transaction...")
        txid = input("Enter txid: ")
        while txid != "end":
            layer, tx = self.find_transaction(txid)
            print(f"Tx found at layer {layer}: {tx}\n\n")
            txid = input("Enter txid: ")

    def find_transaction(self, txid):
        for layer in range(self.nb_layers + 1):
            for tx in self.transaction_lists[layer]:
                if tx.txid == txid:
                    return layer, tx
        return None, None

    def check_duplicates(self):
        for layer in range(self.nb_layers + 1):
            diff_tx = set()
            diff_tx.update(self.transaction_lists[layer])
            if len(list(diff_tx)) != len(self.transaction_lists[layer]):
                print(f"Layer {layer} has duplicated transactions!")
            else:
                print(f"Layer {layer} is clean.")


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
