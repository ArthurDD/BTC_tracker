import pygraphviz as pgv


class GraphVisualisation:
    def __init__(self, transaction_lists):
        self.transaction_lists = transaction_lists
        self.depth = len(transaction_lists)
        self.tree = pgv.AGraph()
        self.root_address = self.transaction_lists[0][0].output_addresses[0]

    def build_tree(self):
        self.tree.add_node(self.root_address)
        for layer in range(self.depth - 1):
            if layer == 0:
                for tx in self.transaction_lists[layer]:
                    self.tree.add_edge(self.root_address, tx.txid)
            elif layer == 1:
                for tx in self.transaction_lists[layer]:
                    for txx in self.transaction_lists[layer + 1]:
                        if txx.prev_txid == tx.txid:
                            self.tree.add_edge(tx.txid, txx.txid)
        self.tree.layout()
        self.tree.draw("graph.png")
        print("Tree done!")

    def find_children(self, tx, layer_counter):
        children = []
        for txx in self.transaction_lists[layer_counter + 1]:
            if txx.prev_txid == tx.id:
                children.append(txx)
        return children
