class GraphVisualisation:
    def __init__(self, transaction_list):
        self.transaction_list = transaction_list
        self.depth = len(transaction_list)
        self.tree = dict()

    # def build_tree(self):
