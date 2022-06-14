from web_scraper import *
from chain_parser import *


def main():
    # address = "bc1qc7fzv8z3damq0vrzn8se8rym8lhell4mwh25g4"
    address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    # try_scraper(address)
    try_parser(address)


def try_scraper(address):
    web_scraper = Scraper(address)
    web_scraper.bitcoinabuse_search()
    web_scraper.google_search()
    web_scraper.twitter_search()
    web_scraper.reddit_search("Arthur")


def try_parser(address):
    chain_parser = ChainParser(address, 1)
    chain_parser.retrieve_transaction_ids()


if __name__ == "__main__":
    main()
