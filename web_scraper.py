import os
import time
from datetime import timedelta

import requests
import requests_cache
from requests.exceptions import HTTPError
import json
from functools import partial

from transformers import BertTokenizer

from bitcoin_abuse.bert_model import BertBA
from bitcoin_abuse.evaluate import predict_BA

FILE_DIR = os.path.dirname(os.path.abspath(__file__))


class Scraper:
    def __init__(self, address="", session=None, send_fct=None):
        if session is None:
            self.session = requests_cache.CachedSession('parser_cache',
                                                        cache_control=True,
                                                        # Use Cache-Control headers for expiration, if available
                                                        expire_after=timedelta(days=14),
                                                        # Otherwise expire responses after 14 days)
                                                        )
        else:
            self.session = session

        self.address = address
        self.bitcoinabuse_ids: dict = {}  # {'abuse_id': 'abuse_type, ...}
        self.send_fct = send_fct

        credentials = self.setup()
        if 'bitcoinabuse' in credentials:
            self.bitcoinabuse_token: str = credentials['bitcoinabuse']['token']

            self.BA_predict = partial(predict_BA)
            self.ba_on = True
            self.ba_wait = False
            self.ba_time = 0
        else:
            self.ba_on = False

        if 'google' in credentials:
            self.google_keywords: list = self.get_google_keywords()
            self.google_custom_search_api_key: str = credentials['google']['custom_search_api_key']
            self.google_custom_engine_id: str = credentials['google']['custom_engine_id']
            self.google_on = True
        else:
            self.google_on = False

        if 'twitter' in credentials:
            self.twitter_bearer_token = credentials['twitter']['bearer_token']
            self.twitter_on = True
        else:
            self.twitter_on = False

        if 'reddit' in credentials:
            self.reddit_client_id = credentials['reddit']['client_id']
            self.reddit_secret_token = credentials['reddit']['secret_token']
            self.reddit_username = credentials['reddit']['username']
            self.reddit_password = credentials['reddit']['password']

            self.reddit_access_token = self.get_reddit_token()

            self.reddit_on = True
        else:
            self.reddit_on = False

        self.result_dict = dict()  # Dict where all information is gathered

    def setup(self) -> dict:
        """
        Get the abuse types from bitcoinabuse.com and retrieves the bitcoinabuse API token from credentials.json
        :return: bitcoinabuse API token
        """
        if self.send_fct is not None:
            self.send_fct(message="Setting up the web scraper...")
        try:
            req = self.session.get(f"https://www.bitcoinabuse.com/api/abuse-types")

            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:  # In case of success
            for pair in req.json():
                self.bitcoinabuse_ids[pair['id']] = pair['label']
            with open(f"{FILE_DIR}/credentials.json", "r") as f:
                dic = json.load(f)
            return dic

    def start_scraping(self):
        """
        Builds self.result_dict by querying every API configured.
        :return: dict self.result_dict
        """
        if self.send_fct is not None:
            self.send_fct(message="Set up done! Starting scraping websites...")
        self.result_dict['bitcoin_abuse'] = self.bitcoinabuse_search()
        self.result_dict['twitter'] = self.twitter_search()
        self.result_dict['google'] = self.google_search()
        self.result_dict['reddit'] = self.reddit_search()
        self.result_dict['address'] = self.address

        self.result_dict['apis_on'] = ['BitcoinAbuse' if self.ba_on else None, 'Twitter' if self.twitter_on else None,
                                       'Google' if self.google_on else None, 'Reddit' if self.reddit_on else None]
        self.result_dict['apis_on'] = ", ".join([elt for elt in self.result_dict['apis_on'] if elt is not None])
        return self.result_dict

    def bitcoinabuse_search(self, address="", display=False) -> dict:
        """
        Get last reports made on the address in input.
        :param address: Address to find information for
        :param display: Whether we print information or we return them.
        :return: dict of information about the reports
        """
        if not self.ba_on:
            return {'found': False, 'address': address}

        self.check_ba_wait()
        if not self.ba_wait:
            if not address:
                address = self.address

            nb_tries = 0
            while nb_tries < 5 and not self.ba_wait:
                try:
                    link = f"https://www.bitcoinabuse.com/api/reports/check?address={address}" \
                           f"&api_token={self.bitcoinabuse_token}"
                    # print(f"Link is: {link}")
                    req = self.session.get(link)

                    # If the response was successful, no Exception will be raised
                    req.raise_for_status()
                except Exception as err:
                    if "Too Many Requests" in str(err):
                        self.ba_wait = True
                        self.ba_time = time.time()
                    else:
                        nb_tries += 1
                        if nb_tries >= 5:
                            print(f"bitcoinabuse_search - Error occurred: {err} \n"
                                  f"Can't retrieve information for address {address}\n")
                        else:
                            print(f'bitcoinabuse_search - Error occurred: {err} \nRetrying in 3s...')
                            time.sleep(3)  # Sleep for 3 seconds to make the request again
                else:
                    content = req.json()
                    if content['count'] > 0:
                        abuse_type_dict = {f'{key}': 0 for key in self.bitcoinabuse_ids.values()}

                        if self.BA_predict is not None:
                            for i in range(len(content['recent']) - 1, -1, -1):
                                # If it's a genuine report:
                                if self.BA_predict(content['recent'][i]['description']) == 1:
                                    # Count abuse types
                                    abuse_type_dict[self.bitcoinabuse_ids[content['recent'][i]['abuse_type_id']]] += 1
                                else:  # We remove fake reports
                                    content['recent'].pop(i)
                        if display:
                            print(f"Address ({address[:10]}...)reported {content['count']} time(s) in the past: "
                                  f"(Last time reported: {content['last_seen']})")
                            print("Recent reports:\n" + '\n'.join([f"- {self.bitcoinabuse_ids[elt['abuse_type_id']]}:  "
                                                                   f"{elt['description']}"
                                                                   for elt in content['recent']]))

                        return {'found': True, 'address': address, 'total_report_count': content['count'],
                                'last_reported': content['last_seen'], 'genuine_report': content['recent'],
                                'genuine_recent_count': len(content['recent']), 'report_types': abuse_type_dict}
                    else:
                        # print(f"This address has never been reported before.")
                        return {'found': False, 'address': address}

            # We only get here if we failed to make the request 5 times.
            return {'found': False, 'address': address}

    def check_ba_wait(self):
        if not self.ba_wait:
            return
        elif time.time() - self.ba_time > 60:
            self.ba_wait = False
        else:
            return

    @staticmethod
    def get_google_keywords() -> list:
        """
        Gets keywords from keywords.txt.
        :return: list of str keywords
        """
        keywords = []
        with open(f"{FILE_DIR}/keywords.txt", "r") as f:
            for line in f.readlines():
                if line:
                    keywords.append(line.strip())
        return keywords

    def google_search(self, address="", display=False) -> dict:
        """
        Gets potentially useful information from Google.
        """
        if not self.google_on:
            return {'found': False}

        if not address:
            address = self.address
        try:
            params = {'cx': self.google_custom_engine_id, 'q': address, 'key': self.google_custom_search_api_key}
            req = self.session.get("https://customsearch.googleapis.com/customsearch/v1", params=params)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:
            content = req.json()
            search_info = content['searchInformation']
            if int(search_info['totalResults']) > 0:
                relevant_results = []
                for elt in content['items']:
                    for keyword in self.google_keywords:
                        if keyword in elt['title'] or keyword in elt['link']:
                            relevant_results.append(elt)
                            break
                if display:
                    print(f"Total results: {search_info['totalResults']}")
                    print(
                        f"Relevant results:\n" + '\n'.join(f"{elt['title'], elt['link']}" for elt in relevant_results))
                return {'found': True, 'relevant_results': relevant_results,
                        'nb_results': len(relevant_results)}
            else:
                if display:
                    print("No results found.")
                return {'found': False}

    def twitter_search(self, address="", display=False) -> dict:
        """
        Gets potentially useful information from Twitter
        :return: None
        """
        if not self.twitter_on:
            return {'found': False}

        if not address:
            address = self.address

        query = f"{address} lang:en -is:retweet -is:reply -is:quote"
        tweet_fields = "text,author_id,created_at,source"
        try:
            headers = {"Authorization": f"Bearer {self.twitter_bearer_token}"}
            params = {'query': query, 'tweet.fields': {tweet_fields}, 'max_results': 10}

            response = self.session.get("https://api.twitter.com/2/tweets/search/recent",
                                        headers=headers, params=params)

            # To get user's username from its ID
            # response2 = self.session.get("https://api.twitter.com/2/users/1451510344329965570", headers=headers)

        except HTTPError as http_err:
            if display:
                print(f'HTTP error occurred: {http_err}')
            return {'found': False, 'reason': 'HTTP error'}
        except Exception as err:
            if display:
                print(f'Other error occurred: {err}')
            return {'found': False, 'reason': 'Request error'}

        else:
            content = response.json()
            if display:
                print(json.dumps(response.json(), indent=4, sort_keys=True))

            if content['meta']['result_count'] > 0:  # https://twitter.com/{user_id or username}/status/{tweet_id}
                response_dict = {'found': True, 'nb_results': content['meta']['result_count'], 'results': []}
                for elt in content['data']:
                    link = f"https://twitter.com/{elt['author_id']}/status/{elt['id']}"
                    response_dict['results'].append((link, elt['text']))
                return response_dict

            else:
                return {'found': False}

    def get_reddit_token(self) -> str:
        data = {'grant_type': 'password',
                'username': f"{self.reddit_username}",
                'password': f"{self.reddit_password}"}
        auth = requests.auth.HTTPBasicAuth(self.reddit_client_id, self.reddit_secret_token)

        headers = {'User-Agent': 'BTC_Tracker/0.0.1'}

        access_token = ""
        token_req = False
        counter = 0
        # We try at most 100 times to get the token if the request fails
        while not token_req and counter < 5:
            try:
                counter += 1
                response = requests.post('https://www.reddit.com/api/v1/access_token',
                                         auth=auth, data=data, headers=headers)
                access_token = response.json()['access_token']
            except KeyError:
                pass
            else:
                token_req = True
        if not token_req:
            raise "Error while requesting reddit access token."
        return access_token

    def reddit_search(self, address="", display=False) -> dict:
        """
        Gets potentially useful information from Reddit
        :return: None
        """
        if not self.reddit_on:
            return {'found': False}

        if not address:
            address = self.address

        if not self.reddit_access_token:
            if display:
                print(f"Could not retrieve any information from Reddit, "
                      f"invalid access token! (={self.reddit_access_token})")
            return {'found': False, 'reason': "Invalid Token"}

        # add authorization to our headers dictionary
        headers = {'User-Agent': 'BTC_Tracker/0.0.1', 'Authorization': f"bearer {self.reddit_access_token}"}
        self.session.get('https://oauth.reddit.com/api/v1/me', headers=headers)

        try:
            req = self.session.get(f"https://oauth.reddit.com/search?q={address}",
                                   headers=headers)
            req.raise_for_status()
        except HTTPError as http_err:
            if req.status_code == 401:  # If the token is not valid anymore, we request a new one
                self.reddit_access_token = self.get_reddit_token()
                self.reddit_search(address)  # And we start the search again
            else:
                if display:
                    print(f'HTTP error occurred: {http_err}')
                return {'found': False, 'reason': "HTTP error"}
        except Exception as err:
            if display:
                print(f'Other error occurred: {err}')
            return {'found': False, 'reason': "HTTP error"}

        else:  # In case of success
            content = req.json()
            if len(content['data']['children']) > 0:
                response_dict = {'found': True, 'nb_results': len(content['data']['children']), 'results': []}
                data = content['data']['children']
                for elt in data:
                    response_dict['results'].append((elt['data']['url'], elt['data']['title']))
            else:
                response_dict = {'found': False}

            if display:
                print(response_dict)
            return response_dict


