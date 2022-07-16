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
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                if tx.prev_txid:  # Only not for the layer 0
                    for prev_tuple in tx.prev_txid:
                        prev_txid = prev_tuple[0]
                        if not tx.is_pruned:
                            self.dot.edge(prev_txid, tx.txid)
                        else:
                            self.dot.edge(prev_txid, tx.txid, style='dashed, bold', color="azure3")
        self.add_labels()
        # self.set_special()
        self.set_low_rto()
        self.make_legend()
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
                    self.dot.node(tx.txid, style='filled', fillcolor='orange',
                                  label=rf"{tx.txid[:8]}...\n{tx.amount} BTC \n{tx.tag}\n{tx.rto} RTO")

    def set_special(self):
        """
        DEPRECATED
        Change the border colour for special transactions (see Transaction Class)
        :return: None
        """
        for layer in range(1, self.depth):
            for tx in self.transaction_lists[layer]:
                for txx in self.transaction_lists[layer - 1]:
                    if tx.prev_txid == txx.txid and txx.is_pruned:
                        self.dot.edge(txx.txid, tx.txid, style='dashed, bold', color="azure3")
                        # self.dot.node(tx.txid, color='green', style='filled', fillcolor='lightblue2')

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
        # for layer in range(self.depth - 1):
        #     # txid_list = get_prev_transaction_ids(self.transaction_lists[layer])
        #     for tx in self.transaction_lists[layer]:
        #         # if not tx.is_pruned and not tx.tag and tx.txid not in txid_list:
        #         if tx.is_below_rto_threshold:
        #             print(f"Below threshold: {tx}")
        #             # If this tx has nothing special and is not linked to any future transaction

    def make_legend(self):
        with self.dot.subgraph(name='cluster_legend') as c:
            c.attr(label="Legend", color='blue')
            c.node("pruned_tx", label="", penwidth='0')
            c.node("pruned_tx_end", label="", penwidth='0')
            c.edge("pruned_tx", "pruned_tx_end", label="Pruned Tx", style='dashed, bold', color="azure3")
            c.node("low_rto", label="Low RTO", color='blue', style='filled', fillcolor='azure3')
            c.node("tagged_tx", label="Tagged TX", color='orange', style='filled', fillcolor='orange')
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
