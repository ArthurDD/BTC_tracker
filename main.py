from web_scraper import *


def main():
    address = "bc1qc7fzv8z3damq0vrzn8se8rym8lhell4mwh25g4"

    bitcoinabuse_ids = {}
    bitcoinabuse_token = setup(bitcoinabuse_ids)
    bitcoin_abuse_search(address, bitcoinabuse_ids, bitcoinabuse_token)


if __name__ == "__main__":
    main()