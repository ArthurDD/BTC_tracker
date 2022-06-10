import requests
from requests.exceptions import HTTPError
import json


def setup(bitcoin_abuse_ids):
    # Get the abuse types from bitcoinabuse.com
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
            bitcoin_abuse_token = dic['bitcoinabuse']['token']
            print(f"Bitcoinabuse_token: {bitcoin_abuse_token}")
        return bitcoin_abuse_token


def bitcoin_abuse_search(address, bitcoin_abuse_ids, token):
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
