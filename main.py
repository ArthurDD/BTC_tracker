from web_scraper import *


def main():
    # address = "bc1qc7fzv8z3damq0vrzn8se8rym8lhell4mwh25g4"
    address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    bitcoinabuse_ids = {}
    credentials = setup(bitcoinabuse_ids)
    # bitcoin_abuse_search(address, bitcoinabuse_ids, credentials['bitcoinabuse']['token'])

    # google_search(address,
    #               credentials['google']['custom_search_api_key'],
    #               credentials['google']['custom_engine_id'])

    # search_twitter(address, credentials['twitter']['bearer_token'])

    search_reddit(address, credentials['reddit']['client_id'], credentials['reddit']['secret_token'],
                  credentials['reddit']['username'], credentials['reddit']['password'])


if __name__ == "__main__":
    main()
