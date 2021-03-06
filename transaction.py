class Transaction:
    def __init__(self, txid, prev_txid=None, output_addresses=None, amount=0, rto=0, is_pruned=None):  # rto_threshold=0
        """

        :param txid: Transaction ID of that transaction
        :param prev_txid: List of tuples of the transaction ID to which that tx is linked with the previous layer and
        the layer of the previous transaction. [(prev_txid1, layer1), (prev_txid2, layer2),...]
        :param output_addresses: List of addresses.
        :param amount: amount of BTC output in this tx only according to output_addresses
        """
        if output_addresses is None:
            output_addresses = []
        if prev_txid is None:
            prev_txid = []
        self.txid = txid
        self.prev_txid = prev_txid
        self.output_addresses = output_addresses
        self.amount = amount
        self.rto = rto  # Ratio To Original - contains the amount of original btc that the transaction is supposed to
        # represent
        self.tag = None
        self.is_pruned = is_pruned     # Used to indicate if we pruned the tree based on that tx
        self.is_manually_deleted = False
        self.colour = None  # Only used to display the graph

    def __str__(self):
        return str(self.__dict__)


def find_transaction(tx_lists, txid, layer=None):
    if layer is not None:
        # print(f"Layer given")
        for i, tx in enumerate(tx_lists[layer]):
            if tx.txid == txid:
                return i
        return -1
    else:
        # print(f"Layer not given")
        for layer, tx_list in tx_lists.items():
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
