import os
import random

import graphviz
import numpy as np

from transaction import find_transaction
from pastelor import generate_pastel_colours

FILE_DIR = os.path.dirname(os.path.abspath(__file__))


class GraphVisualisation:
    def __init__(self, transaction_lists, display=False, until=None, forward_transaction_lists=None):
        self.transaction_lists = transaction_lists
        self.forward_transaction_lists = forward_transaction_lists

        self.depth = len(transaction_lists) if until is None else until
        self.forward_depth = 0 if forward_transaction_lists is None else len(forward_transaction_lists)
        self.name = f'transaction-graph-{self.depth - 1}'
        self.dot = graphviz.Digraph(f'transaction-graph-{self.depth - 1}', comment='Transaction Graph', format='svg')
        self.dot.id = "id_test"
        self.dot.graph_attr['rankdir'] = 'LR'
        self.root_address = self.transaction_lists[0][0].output_addresses[0]
        self.display = display      # Indicates whether we want to open the graph at the end of the build.

        self.root_value = sum([tx.amount for tx in self.transaction_lists[0]])

        self.pastel_colours = generate_pastel_colours()

        self.input_addresses = dict()   # Dict containing input addresses of each txid (key=txid and value=address)

    def build_tree(self):
        self.get_input_addresses()
        self.dot.node_attr['shape'] = 'record'
        self.dot.node('root', rf"{self.root_address}\nReceived: {self.root_value} BTC")

        # First, we add all the nodes to the graph
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                self.dot.node(tx.txid, label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0" href="''' + str(self.input_addresses[tx.txid]) + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.root_value*100, 2)) + '''%)</td></tr></table>>''')

        # Add edges between the root node (= input address) and its associated transactions
        self.dot.edges((add.txid, 'root') for add in self.transaction_lists[0])

        # Add all the edges between the different layers.
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.prev_txid:  # Only not for the layer 0
                    for prev_tuple in tx.prev_txid:
                        prev_txid = prev_tuple[0]
                        layer, tx_index = find_transaction(self.transaction_lists, prev_txid)
                        prev_tx = self.transaction_lists[layer][tx_index]
                        if not prev_tx.is_pruned:
                            self.dot.edge(tx.txid, prev_txid)
                        else:
                            self.dot.edge(tx.txid, prev_txid, style='dashed, bold', color="azure3")

        print(f"self.forward_transaction_lists: {self.forward_transaction_lists}")
        if self.forward_transaction_lists is not None:
            print(f"Should work????")
            self.build_forward_graph()

        self.colorize_nodes()
        self.add_labels()
        self.set_low_rto()
        self.set_removed()
        # self.make_legend()
        self.dot.render(directory=f'{FILE_DIR}/doctest-output', view=self.display)

        print(f"Tree done! ({self.name})")
        return f"{self.name}.gv.svg"

    def build_forward_graph(self):
        depth = len(self.forward_transaction_lists)

        # We first build all the nodes
        for layer in range(depth):
            for tx in self.forward_transaction_lists[layer]:
                self.dot.node(tx.txid, label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0" href="''' + str("self.input_addresses[tx.txid]") + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.root_value*100, 2)) + '''%)</td></tr></table>>''')

        # Add edges between the root node (= input address) and its associated transactions
        self.dot.edges(('root', add.txid) for add in self.forward_transaction_lists[0])

        # Add all the edges between the different layers.
        for layer in range(0, depth):
            for tx in self.forward_transaction_lists[layer]:
                if tx.prev_txid:  # Only not for the layer 0
                    for prev_tuple in tx.prev_txid:
                        prev_txid = prev_tuple[0]
                        layer, tx_index = find_transaction(self.forward_transaction_lists, prev_txid)
                        prev_tx = self.forward_transaction_lists[layer][tx_index]
                        if not prev_tx.is_pruned:
                            self.dot.edge(prev_txid, tx.txid)
                        else:
                            self.dot.edge(tx.txid, prev_txid, style='dashed, bold', color="azure3")

    def colorize_nodes(self):
        if self.forward_transaction_lists is not None:
            tx_lists_list = [self.transaction_lists, self.forward_transaction_lists]
        else:
            tx_lists_list = [self.transaction_lists]
        for transaction_lists in tx_lists_list:
            for tx in transaction_lists[0]:
                if not tx.colour:
                    colour = random.choice(self.pastel_colours)
                    tx.colour = colour
                self.dot.node(tx.txid, style='filled', fillcolor=tx.colour)

            for layer in range(1, len(transaction_lists)):
                for tx in transaction_lists[layer]:
                    if len(set(tx.prev_txid)) > 1:
                        tx.colour = random.choice(self.pastel_colours)
                    else:
                        index = find_transaction(transaction_lists, tx.prev_txid[0][0], tx.prev_txid[0][1])
                        prev_tx = transaction_lists[tx.prev_txid[0][1]][index]
                        tx.colour = prev_tx.colour
                    self.dot.node(tx.txid, style='filled', fillcolor=tx.colour)

    def add_labels(self):
        """
        Changes the color of the identified nodes
        :return: None
        """
        for layer in range(self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.tag:
                    self.dot.node(tx.txid, style='filled', fillcolor='orange', label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0">''' + tx.tag + '''</td></tr><tr><td border="0" href="''' + str(self.input_addresses[tx.txid]) + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.root_value*100, 2)) + '''%)</td></tr></table>>''')

        if self.forward_transaction_lists is not None:
            for layer in range(self.forward_depth):
                for tx in self.forward_transaction_lists[layer]:
                    if tx.tag:
                        self.dot.node(tx.txid, style='filled', fillcolor='orange', label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0">''' + tx.tag + '''</td></tr><tr><td border="0" href="''' + str("self.input_addresses[tx.txid]") + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.root_value*100, 2)) + '''%)</td></tr></table>>''')

    def set_removed(self):
        """
        Change the border colour for deleted transactions (see Transaction Class)
        :return: None
        """
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.is_manually_deleted:  # If the user decided not to keep that transaction
                    self.dot.node(tx.txid, color='gray', style='filled', fillcolor='gray51')

    def set_low_rto(self):
        """
        Change the border colour for transactions whose all inputs didn't have enough RTO to be kept
        (colours the transaction before)
        :return: None
        """
        txid_set, prev_txid_set = self.get_all_txids()
        nodes_to_highlight = list(txid_set - prev_txid_set)
        for txid in nodes_to_highlight:
            self.dot.node(txid, color='blue', style='filled', fillcolor='azure3')

    def make_legend(self):
        with self.dot.subgraph(name='cluster_legend') as c:
            c.attr(label="Legend", color='blue')
            c.node("pruned_tx", label="", penwidth='0')
            c.node("pruned_tx_end", label="", penwidth='0')
            c.edge("pruned_tx", "pruned_tx_end", label="Pruned Tx", style='dashed, bold', color="azure3")
            c.node("low_rto", label="Low RTO", color='blue', style='filled', fillcolor='azure3')
            c.node("tagged_tx", label="Tagged TX", color='orange', style='filled', fillcolor='orange')
            c.node("removed_tx", label="Removed Transactions", color='gray', style='filled', fillcolor='gray51')
            c.node("reported_add", label="Reported Address", color='red', style='bold')

    def get_all_txids(self):
        """
        Gets all txids and prev_txids from the transaction_lists in order to find nodes whose inputs' RTO were too low
        to be explored.
        We don't take into consideration transactions that have been tagged (i.e. tx.tag != None)
        :return: 2 sets, txid_set and prev_txid_set.
        """
        txid_set = set()
        prev_txid_set = set()
        for layer in range(self.depth):
            for tx in self.transaction_lists[layer]:
                prev_txid_set.update([prev_txid[0] for prev_txid in tx.prev_txid])
                if layer != self.depth - 1 and tx.tag is None:
                    txid_set.add(tx.txid)
        return txid_set, prev_txid_set

    @staticmethod
    def get_colours(self):
        colours = []
        with open(FILE_DIR + '/colours.txt', 'r') as f:
            for line in f.readlines():
                if line.strip():
                    colours.append(line.strip())
        return colours

    def get_input_addresses(self):
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.txid not in self.input_addresses:
                    self.input_addresses[tx.txid] = None
                for txid, prev_layer in tx.prev_txid:
                    self.input_addresses[txid] = tx.output_addresses[0]
