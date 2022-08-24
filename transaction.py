class Transaction:
    def __init__(self, txid, prev_txid=None, output_addresses=None, input_addresses=None,
                 amount=0, rto=0, is_pruned=None, tag=None):
        """
        :param txid: Transaction ID of that transaction
        :param prev_txid: List of tuples of the transaction ID to which that tx is linked with the previous layer and
        the layer of the previous transaction. [(prev_txid1, layer1), (prev_txid2, layer2),...]
        :param output_addresses: List of addresses.
        :param amount: amount of BTC output in this tx only according to output_addresses
        """
        if output_addresses is None:
            output_addresses = []
        if input_addresses is None:
            input_addresses = []
        if prev_txid is None:
            prev_txid = []
        self.txid = txid
        self.prev_txid = prev_txid
        self.output_addresses = output_addresses    # Contains output addresses for the backward parsing (pointing to
        # our output(s) of the transaction)
        self.input_addresses = input_addresses   # Contains input addresses for the forward parsing (point to
        # our input(s) of the transaction)
        self.amount = amount
        self.rto = rto  # Ratio To Original - contains the amount of original btc that the transaction is supposed to
        # represent
        self.tag = tag
        self.is_pruned = is_pruned     # Used to indicate if we pruned the tree based on that tx
        self.is_manually_deleted = False
        self.colour = None  # Only used to display the graph

    def __str__(self):
        return str(self.__dict__)


def find_transaction(tx_lists, txid, layer=None, start_index=None, stop_index=None):
    if layer is not None:
        for i, tx in enumerate(tx_lists[layer]):
            if tx.txid == txid:
                return i
        return -1
    else:
        if start_index is None:
            start_index = 0
        if stop_index is None:
            stop_index = len(tx_lists)
        for layer in range(start_index, stop_index):
            tx_list = tx_lists[layer]
            for i, tx in enumerate(tx_list):
                if tx.txid == txid:
                    return layer, i
        return -1, -1


def get_prev_transaction_ids(tx_list):
    """
    Takes a list of tx as input and returns all of their previous transaction ids
    :param tx_list: list of transactions
    :return: List of tx_ids
    """
    id_list = set()
    for tx in tx_list:
        id_list.update([elt[0] for elt in tx.prev_txid])
    return list(id_list)
