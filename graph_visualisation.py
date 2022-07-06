import graphviz

from transaction import get_prev_transaction_ids


class GraphVisualisation:
    def __init__(self, transaction_lists):
        self.transaction_lists = transaction_lists
        self.depth = len(transaction_lists)
        self.dot = graphviz.Digraph(f'transaction-graph-{self.depth - 1}', comment='Transaction Graph', format='jpeg')
        self.dot.graph_attr['rankdir'] = 'LR'
        self.root_address = self.transaction_lists[0][0].output_addresses[0]

        self.root_value = sum([tx.amount for tx in self.transaction_lists[0]])

    def build_tree(self):
        self.dot.node_attr['shape'] = 'record'
        self.dot.node('root', rf"{self.root_address}\nReceived: {self.root_value} BTC")
        # First, we add all the nodes to the graph
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                self.dot.node(tx.txid, label=rf"{tx.txid[:8]}...\n {tx.amount} BTC\n{tx.rto} RTO")

        # Add edges between the root node (= input address) and its associated transactions
        self.dot.edges(('root', add.txid) for add in self.transaction_lists[0])

        # Add all the edges between the different layers.
        for layer in range(1, self.depth):
            for tx in self.transaction_lists[layer]:
                for txx in self.transaction_lists[layer - 1]:
                    if tx.prev_txid == txx.txid:
                        self.dot.edge(txx.txid, tx.txid)
        self.add_labels()
        self.set_special()
        self.set_low_rto()
        self.dot.render(directory='doctest-output', view=True)
        print("Tree done!")

    def add_labels(self):
        """
        Changes the color of the identified nodes
        :return: None
        """
        for layer in range(self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.tag:
                    self.dot.node(tx.txid, color='red', style='filled, bold', fillcolor='orange',
                                  label=rf"{tx.txid[:8]}...\n{tx.amount} BTC \n{tx.tag}\n{tx.rto} RTO")

    def set_special(self):
        """
        Change the border colour for special transactions (see Transaction Class)
        :return: None
        """
        for layer in range(self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.is_special and tx.tag is None:
                    self.dot.node(tx.txid, color='green', style='filled', fillcolor='lightblue2')

    def set_low_rto(self):
        """
        Change the border colour for transactions that did not have enough RTO to be kept
        (colours the transaction before)
        :return: None
        """
        for layer in range(self.depth - 1):
            txid_list = get_prev_transaction_ids(self.transaction_lists[layer + 1])
            for tx in self.transaction_lists[layer]:
                if not tx.is_special and not tx.tag and tx.txid not in txid_list:
                    # If this tx has nothing special and is not linked to any future transaction
                    self.dot.node(tx.txid, color='blue', style='filled', fillcolor='azure3')
