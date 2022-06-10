import requests
from requests.exceptions import HTTPError
import json


def setup(bitcoin_abuse_ids):
    """
    Get the abuse types from bitcoinabuse.com and retrieves the bitcoinabuse API token from credentials.json
    :param bitcoin_abuse_ids: dict to be filled with abuse_ids as keys and abuse_types as items
    {'abuse_id': 'abuse_type, ...}
    :return: bitcoinabuse API token
    """
    try:
        req = requests.get(f"https://www.bitcoinabuse.com/api/abuse-types")

        # If the response was successful, no Exception will be raised
        req.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')
    else:  # In case of success
        for pair in req.json():
            bitcoin_abuse_ids[pair['id']] = pair['label']
        with open("credentials.json", "r") as f:
            dic = json.load(f)
        return dic


def bitcoin_abuse_search(address, bitcoin_abuse_ids, token):
    """
    Get last reports made on the address in input.
    :param address: BTC address to look up abuses for.
    :param bitcoin_abuse_ids: dict of ids and their associated abuse types.
    :param token: Bitcoinabuse API token.
    :return: None
    """

    try:
        req = requests.get(f"https://www.bitcoinabuse.com/api/reports/check?address={address}&api_token={token}")

        # If the response was successful, no Exception will be raised
        req.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except Exception as err:
        print(f'Other error occurred: {err}')  # Python 3.6
    else:
        print('Success!')
        content = req.json()
        if content['count'] > 0:
            print(f"Address reported {content['count']} time(s) in the past: "
                  f"(Last time reported: {content['last_seen']})")
            print("Recent reports:\n" + '\n'.join([f"- {bitcoin_abuse_ids[elt['abuse_type_id']]}:  {elt['description']}"
                                                   for elt in content['recent']]))
        else:
            print(f"This address has never been reported before.")


def get_keywords():
    """
    Gets keywords from keywords.txt.
    :return: list of str keywords
    """
    keywords = []
    with open("keywords.txt", "r") as f:
        for line in f.readlines():
            if line:
                keywords.append(line.strip())
    return keywords


def google_search(address, custom_search_api_key, custom_engine_id):
    """
    Gets potentially useful information from Google.
    :param custom_engine_id: Custom engine ID (cx)
    :param custom_search_api_key: Custom search API key
    :param address: Address to look up information for.
    :return: None
    """
    print(f"custom_search_api_key: {custom_search_api_key}")
    try:
        params = {'cx': custom_engine_id, 'q': address, 'key': custom_search_api_key}
        req = requests.get("https://customsearch.googleapis.com/customsearch/v1?", params=params)
        # If the response was successful, no Exception will be raised
        req.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')
    else:
        print('Success!')
        keywords = get_keywords()

        content = req.json()
        search_info = content['searchInformation']
        print(f"Total results: {search_info['totalResults']}")
        if int(search_info['totalResults']) > 0:
            relevant_results = []
            for elt in content['items']:
                for keyword in keywords:
                    if keyword in elt['title'] or keyword in elt['link']:
                        relevant_results.append(elt)
                        break

            print(f"Relevant results:\n" + '\n'.join(f"{elt['title'], elt['link']}" for elt in relevant_results))
        else:
            print("No results found.")
