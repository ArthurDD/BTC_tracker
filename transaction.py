class Transaction:
    def __init__(self, txid, prev_txid=None, output_addresses=None, amount=0, rto=0, is_pruned=None, rto_threshold=0):
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
        self.is_below_rto_threshold = False if rto > rto_threshold else True
        self.tag = None
        self.is_pruned = is_pruned     # Used to indicate if we pruned the tree based on that tx

    def __str__(self):
        # print(f"'txid': {self.txid}, 'next_txid': {self.next_txid}, 'output_addresses': {self.output_addresses}, "
        #       f"'amount': {self.amount}, 'tag': {self.tag}")
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
    id_list = set()
    for tx in tx_list:
        id_list.update([elt[0] for elt in tx.prev_txid])
    return list(id_list)
