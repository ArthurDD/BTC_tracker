from web_scraper import *


def main():
    # address = "bc1qc7fzv8z3damq0vrzn8se8rym8lhell4mwh25g4"
    address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    web_scraper = Scraper(address)
    # web_scraper.bitcoinabuse_search()

    # web_scraper.google_search()

    # web_scraper.twitter_search()

    web_scraper.reddit_search("Arthur")


if __name__ == "__main__":
    main()
