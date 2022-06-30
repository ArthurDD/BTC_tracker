import graphviz


class GraphVisualisation:
    def __init__(self, transaction_lists):
        self.transaction_lists = transaction_lists
        self.depth = len(transaction_lists)
        self.dot = graphviz.Digraph('transaction-graph', comment='Transaction Graph', format='png')
        self.dot.graph_attr['rankdir'] = 'LR'
        self.root_address = self.transaction_lists[0][0].output_addresses[0]

    def build_tree(self):
        self.dot.node_attr['shape'] = 'record'
        self.dot.node('root', self.root_address)
        # First, we add all the nodes to the graph
        for layer in range(0, self.depth):
            for tx in self.transaction_lists[layer]:
                self.dot.node(tx.txid, label=rf"{tx.txid[:8]}...\n {tx.amount} BTC")

        # Add edges between the root node (= input address) and its associated transactions
        self.dot.edges(('root', add.txid) for add in self.transaction_lists[0])

        # Add all the edges between the different layers.
        for layer in range(1, self.depth):
            for tx in self.transaction_lists[layer]:
                for txx in self.transaction_lists[layer - 1]:
                    if tx.prev_txid == txx.txid:
                        self.dot.edge(txx.txid, tx.txid)
        self.add_labels()
        self.dot.render(directory='doctest-output', view=True)
        print("Tree done!")

    def add_labels(self):
        """
        Changes the color of the identified nodes
        :return: None
        """
        for layer in range(self.depth):
            print(f"Layer: {layer}")
            for tx in self.transaction_lists[layer]:
                if tx.tag:
                    self.dot.node(tx.txid, color='red', style='filled', fillcolor='lightblue2',
                                  label=rf"{tx.txid[:8]}...\n{tx.amount} BTC \n{tx.tag}")
