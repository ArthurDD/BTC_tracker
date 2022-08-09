import os
import random

import graphviz
import numpy as np

from transaction import find_transaction
from pastelor import generate_pastel_colours

FILE_DIR = os.path.dirname(os.path.abspath(__file__))


class GraphVisualisation:
    def __init__(self, transaction_lists=None, display=False, until=None, backward_layers=0, forward_layers=0,
                 backward_root_value=0, forward_root_value=0):
        self.transaction_lists = transaction_lists

        self.backward_layers = backward_layers
        self.forward_layers = forward_layers

        self.depth = len(transaction_lists) if until is None else until
        self.name = f'transaction-graph-{self.depth}'
        self.dot = graphviz.Digraph(f'transaction-graph-{self.depth}', comment='Transaction Graph', format='svg')
        self.dot.id = "id_test"
        self.dot.graph_attr['rankdir'] = 'LR'
        if backward_layers > 0:
            self.root_address = self.transaction_lists[0][0].output_addresses[0]
        else:
            self.root_address = self.transaction_lists[0][0].input_addresses[0]

        self.display = display  # Indicates whether we want to open the graph at the end of the build.

        if backward_layers > 0:
            self.backward_root_value = backward_root_value
        if forward_layers > 0:
            self.forward_root_value = forward_root_value

        self.pastel_colours = generate_pastel_colours()

        self.input_addresses = dict()  # Dict containing input addresses of each txid (key=txid and value=address)
        self.output_addresses = dict()

        self.txid_set = set()
        self.prev_txid_set = set()

    def build_tree(self):
        self.dot.node_attr['shape'] = 'record'
        if self.backward_layers > 0 and self.depth <= self.backward_layers:
            # Case where only backward tree needs to be built
            self.dot.node('root',
                          rf"{self.root_address}\nReceived: {self.backward_root_value} BTC\n{self.depth} - backward")
            print(f"Building backward only")
            self.build_backward_tree()
            self.get_all_txids(stop_index=self.depth)

        elif self.backward_layers == 0:  # Case when only forward tree needs to be built
            self.dot.node('root', rf"{self.root_address}\nSent: {self.forward_root_value} BTC\n{self.depth} - forward")
            print(f"Building forward only")
            self.build_forward_tree()
            self.get_all_txids(stop_index=self.depth)

        else:  # Here, depth > backward_layers, so we need to build both trees
            self.dot.node('root', rf"{self.root_address}\nReceived: {self.backward_root_value} BTC\n" +
                          rf"Sent: {self.forward_root_value} BTC\n{self.depth} - both")
            print(f"Building backward and forward")
            self.build_backward_tree()
            self.build_forward_tree()
            self.get_all_txids(start_index=0, stop_index=self.backward_layers)  # For the backward tree
            self.get_all_txids(start_index=self.backward_layers, stop_index=self.depth)  # For the forward tree

        self.set_low_rto()
        self.add_labels()
        self.set_removed()

        # self.make_legend()
        self.dot.render(directory=f'{FILE_DIR}/doctest-output', view=self.display)

        print(f"Tree done! ({self.name})")
        return f"{self.name}.gv.svg"

    def build_backward_tree(self):
        depth = min(self.backward_layers, self.depth)
        self.get_input_addresses()

        # First, we add all the nodes to the graph
        for layer in range(0, depth):
            for tx in self.transaction_lists[layer]:
                self.dot.node(tx.txid, label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0" href="''' + str(self.input_addresses[tx.txid]) + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.backward_root_value*100, 2)) + '''%)</td></tr></table>>''')

        # Add edges between the root node (= input address) and its associated transactions
        self.dot.edges((add.txid, 'root') for add in self.transaction_lists[0])

        # Add all the edges between the different layers.
        for layer in range(0, depth):
            for tx in self.transaction_lists[layer]:
                if tx.prev_txid:  # Only not for the layer 0
                    for prev_tuple in tx.prev_txid:
                        prev_txid = prev_tuple[0]
                        layer, tx_index = find_transaction(self.transaction_lists, prev_txid, stop_index=depth)
                        prev_tx = self.transaction_lists[layer][tx_index]
                        if not prev_tx.is_pruned:
                            self.dot.edge(tx.txid, prev_txid)
                        else:
                            self.dot.edge(tx.txid, prev_txid, style='dashed, bold', color="azure3")

        self.colorize_nodes(start_index=0, depth=depth)

    def build_forward_tree(self):
        for layer in range(self.backward_layers, self.depth):
            for tx in self.transaction_lists[layer]:
                self.dot.node(tx.txid, label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0" href="''' + str(tx.input_addresses[0]) + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.forward_root_value*100, 2)) + '''%)</td></tr></table>>''')

        # Add edges between the root node (= input address) and its associated transactions
        self.dot.edges(('root', add.txid) for add in self.transaction_lists[self.backward_layers])

        # Add all the edges between the different layers.
        for layer in range(self.backward_layers, self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.prev_txid:  # Only not for the layer 0
                    for prev_tuple in tx.prev_txid:
                        prev_txid = prev_tuple[0]
                        layer, tx_index = find_transaction(self.transaction_lists, prev_txid,
                                                           start_index=self.backward_layers)
                        prev_tx = self.transaction_lists[layer][tx_index]
                        if not prev_tx.is_pruned:
                            self.dot.edge(prev_txid, tx.txid)
                        else:
                            self.dot.edge(prev_txid, tx.txid, style='dashed, bold', color="azure3")

        self.colorize_nodes(start_index=self.backward_layers, depth=self.depth)
        self.set_unspent_tx()

    def colorize_nodes(self, start_index, depth):
        for tx in self.transaction_lists[start_index]:
            if not tx.colour:
                colour = random.choice(self.pastel_colours)
                tx.colour = colour
            self.dot.node(tx.txid, style='filled', fillcolor=tx.colour)

        for layer in range(start_index + 1, depth):
            for tx in self.transaction_lists[layer]:
                if len(set(tx.prev_txid)) > 1:
                    tx.colour = random.choice(self.pastel_colours)
                else:
                    if start_index < self.backward_layers:  # In the case of the backward tree
                        index = find_transaction(self.transaction_lists, tx.prev_txid[0][0], layer=tx.prev_txid[0][1],
                                                 stop_index=self.backward_layers)
                    else:  # In the case of the forward tree
                        index = find_transaction(self.transaction_lists, tx.prev_txid[0][0], layer=tx.prev_txid[0][1],
                                                 start_index=self.backward_layers)
                    prev_tx = self.transaction_lists[tx.prev_txid[0][1]][index]
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
                    if layer < self.backward_layers:
                        self.dot.node(tx.txid, color='red', style='filled, bold', fillcolor='orange', label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0">''' + tx.tag + '''</td></tr><tr><td border="0" href="''' + str(self.input_addresses[tx.txid]) + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.backward_root_value*100, 2)) + '''%)</td></tr></table>>''')
                    else:
                        self.dot.node(tx.txid, color='red', style='filled, bold', fillcolor='orange', label='''<<table border="0"><tr><td border="0" href="https://www.walletexplorer.com/txid/''' + tx.txid + '''" target="_blank">''' + tx.txid[:8] + '''...</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0">''' + tx.tag + '''</td></tr><tr><td border="0" href="''' + str(tx.input_addresses[0]) + '''">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.forward_root_value*100, 2)) + '''%)</td></tr></table>>''')

    def set_removed(self):
        """
        Change the border colour for deleted transactions (see Transaction Class)
        :return: None
        """
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.is_manually_deleted:  # If the user decided not to keep that transaction
                    self.dot.node(tx.txid, color='gray88', style='filled, bold', fillcolor='gray51')

    def set_low_rto(self):
        """
        Change the border colour for transactions whose all inputs didn't have enough RTO to be kept
        (colours the transaction before)
        :return: None
        """
        nodes_to_highlight = list(self.txid_set - self.prev_txid_set)
        for txid in nodes_to_highlight:
            self.dot.node(txid, color='blue', style='filled, bold', fillcolor='azure3')

    def set_unspent_tx(self):
        """
        Change the colour of the unspent transactions
        """
        for layer in range(self.backward_layers, self.depth):
            for tx in self.transaction_lists[layer]:
                if "unspent_tx" in tx.txid:
                    self.dot.node(tx.txid, color='gray88', shape='ellipse', style='filled', fillcolor='gray51',
                                  label='''<<table border="0"><tr><td border="0">Unspent Tx.</td></tr><tr><td border="0">''' + str(tx.amount) + ''' BTC</td></tr><tr><td border="0">''' + str(np.round(tx.rto, 4)) + ''' RTO (''' + str(np.round(tx.rto/self.forward_root_value*100, 2)) + '''%)</td></tr></table>>''')

    def make_legend(self):
        with self.dot.subgraph(name='cluster_legend') as c:
            c.attr(label="Legend", color='blue')
            c.node("pruned_tx", label="", penwidth='0')
            c.node("pruned_tx_end", label="", penwidth='0')
            c.edge("pruned_tx", "pruned_tx_end", label="Pruned Tx", style='dashed, bold', color="azure3")
            c.node("low_rto", label="Low RTO", color='blue', style='filled, bold', fillcolor='azure3')
            c.node("tagged_tx", label="Tagged TX", color='red', style='filled, bold', fillcolor='orange')
            c.node("removed_tx", label="Removed Transactions", color='gray88', style='filled, bold', fillcolor='gray51')
            c.node("unspent_tx", color='gray88', shape='ellipse', style='filled, bold', fillcolor='gray51',
                   label="Unspent Transactions")

    def get_all_txids(self, start_index=0, stop_index=None):
        """
        Gets all txids and prev_txids from the transaction_lists in order to find nodes whose inputs' RTO were too low
        to be explored.
        We don't take into consideration transactions that have been tagged (i.e. tx.tag != None)
        :return: 2 sets, txid_set and prev_txid_set.
        """
        if stop_index is None:
            stop_index = self.depth
        depth_to_respect = stop_index
        for layer in range(start_index, depth_to_respect):
            for tx in self.transaction_lists[layer]:
                self.prev_txid_set.update([prev_txid[0] for prev_txid in tx.prev_txid])
                if layer < depth_to_respect - 1 and tx.tag is None and "unspent_" not in tx.txid:
                    self.txid_set.add(tx.txid)

    @staticmethod
    def get_colours():
        colours = []
        with open(FILE_DIR + '/colours.txt', 'r') as f:
            for line in f.readlines():
                if line.strip():
                    colours.append(line.strip())
        return colours

    def get_input_addresses(self):
        depth = min(self.depth, self.backward_layers)
        for layer in range(0, depth):
            for tx in self.transaction_lists[layer]:
                if tx.txid not in self.input_addresses:
                    self.input_addresses[tx.txid] = None
                for txid, prev_layer in tx.prev_txid:
                    try:
                        self.input_addresses[txid] = tx.output_addresses[0]
                    except Exception as e:
                        print(f"tx.input_addresses: {tx}")
                        print(f"Error: {e}")
                        raise e

    def get_output_addresses(self):
        """
                                Not used anymore
        Builds a dict of output addresses of each txid ({'txid':output_add, ...})
        """
        for layer in range(self.backward_layers, self.depth):
            for tx in self.transaction_lists[layer]:

                if tx.txid not in self.output_addresses:
                    self.output_addresses[tx.txid] = None
                for txid, prev_layer in tx.prev_txid:
                    try:
                        self.output_addresses[txid] = tx.input_addresses[0]
                    except Exception as e:
                        print(f"tx.input_addresses: {tx}")
                        print(f"Error: {e}")
                        raise e
