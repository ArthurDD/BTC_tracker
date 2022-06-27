class Transaction:
    def __init__(self, txid, prev_txid=None, output_addresses=None, amount=0):
        """

        :param txid: Transaction ID of that transaction
        :param prev_txid: Transaction ID to which that tx is linked with the previous layer
        :param output_addresses: List of addresses.
        :param amount: amount of BTC output in this tx only according to output_addresses
        """
        if output_addresses is None:
            output_addresses = []
        self.txid = txid
        self.prev_txid = prev_txid
        self.output_addresses = output_addresses
        self.amount = amount
        self.tag = None

    def __str__(self):
        # print(f"'txid': {self.txid}, 'next_txid': {self.next_txid}, 'output_addresses': {self.output_addresses}, "
        #       f"'amount': {self.amount}, 'tag': {self.tag}")
        return str(self.__dict__)


def find_transaction(tx_list, txid):
    for i, tx in enumerate(tx_list):
        if tx.txid == txid:
            return i
    return -1
