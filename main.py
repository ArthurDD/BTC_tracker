from chain_parser import *
from graph_visualisation import *


def main():
    # address = "bc1q6u5hsdjvz90fkzzmudz84jqtpdl0vc0yqd3375"
    # address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"  # Satoshi's Address (50 mined BTC)
    address = "115ZFznB6rTteLDF18AQTf2SWNBtoywoxb"  # Smaller address
    # address = "1MTKuR4CHJEZ1qSvoHyE8MDrVs4f1HQP5L"

    # address = "3JMjHDTJjKPnrvS7DycPAgYcA6HrHRk8UG"  # Scam

    scamming_address = "bc1qhuz2x7pceg5el4y94v888em625cgnmn3aewmcd"
    try_scraper(scamming_address)
    # try_parser(address)


def try_scraper(address):
    web_scraper = Scraper(address)
    # resp = web_scraper.bitcoinabuse_search(display=True)
    # print(resp)
    # web_scraper.google_search()
    # resp = web_scraper.twitter_search("Arthur")
    # print(resp)
    web_scraper.reddit_search("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", display=True)


def try_parser(address):
    # Start the parsing
    chain_parser = ChainParser(address, 4)
    res = chain_parser.start_analysis(manual=False)
    if res:
        # chain_parser.get_statistics(display=True)

        # Build the tree
        tree = GraphVisualisation(chain_parser.transaction_lists, display=True)
        tree.build_tree()

        # chain_parser.find_transactions()


if __name__ == "__main__":
    main()
