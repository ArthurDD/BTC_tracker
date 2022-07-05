from web_scraper import *
from chain_parser import *
from graph_visualisation import *


def main():
    address = "bc1q6u5hsdjvz90fkzzmudz84jqtpdl0vc0yqd3375"
    # address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"  # Satoshi's Address (50 mined BTC)
    # address = "115ZFznB6rTteLDF18AQTf2SWNBtoywoxb"  # Smaller address
    # address = "1MTKuR4CHJEZ1qSvoHyE8MDrVs4f1HQP5L"

    # try_scraper(address)
    try_parser(address)


def try_scraper(address):
    web_scraper = Scraper(address)
    web_scraper.bitcoinabuse_search()
    web_scraper.google_search()
    web_scraper.twitter_search()
    web_scraper.reddit_search("Arthur")


def try_parser(address):
    chain_parser = WEChainParser(address, 3)
    # chain_parser.get_wallet_transactions()
    # chain_parser.get_addresses_from_txid()
    chain_parser.start_analysis()
    chain_parser.get_statistics()
    tree = GraphVisualisation(chain_parser.transaction_lists)
    tree.build_tree()
    # chain_parser._get_addresses("https://www.walletexplorer.com/txid/"
    #                             "9934d4518cae3a3ccb0d48b7e617075d4d50329f381a8dd6e2f42fe5545b4efc")

    # chain_parser = BCChainParser(address, 1)
    # chain_parser.get_wallet_transactions()


if __name__ == "__main__":
    main()
