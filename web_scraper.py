import requests
from requests.exceptions import HTTPError
import json


class Scraper:
    def __init__(self, address=""):
        self.address: str = address
        self.bitcoinabuse_ids: dict = {}    # {'abuse_id': 'abuse_type, ...}

        credentials = self.setup()
        self.bitcoinabuse_token: str = credentials['bitcoinabuse']['token']

        self.google_keywords: list = self.get_google_keywords()
        self.google_custom_search_api_key: str = credentials['google']['custom_search_api_key']
        self.google_custom_engine_id: str = credentials['google']['custom_engine_id']

        self.twitter_bearer_token = credentials['twitter']['bearer_token']

        self.reddit_client_id = credentials['reddit']['client_id']
        self.reddit_secret_token = credentials['reddit']['secret_token']
        self.reddit_username = credentials['reddit']['username']
        self.reddit_password = credentials['reddit']['password']

        self.reddit_access_token = self.get_reddit_token()

    def setup(self) -> dict:
        """
        Get the abuse types from bitcoinabuse.com and retrieves the bitcoinabuse API token from credentials.json
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
                self.bitcoinabuse_ids[pair['id']] = pair['label']
            with open("credentials.json", "r") as f:
                dic = json.load(f)
            return dic

    def bitcoinabuse_search(self, address="") -> None:
        """
        Get last reports made on the address in input.
        :return: None
        """
        if not address:
            address = self.address
        try:
            req = requests.get(f"https://www.bitcoinabuse.com/api/reports/check?address={address}"
                               f"&api_token={self.bitcoinabuse_token}")

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
                print("Recent reports:\n" + '\n'.join([f"- {self.bitcoinabuse_ids[elt['abuse_type_id']]}:  {elt['description']}"
                                                       for elt in content['recent']]))
            else:
                print(f"This address has never been reported before.")

    @staticmethod
    def get_google_keywords() -> list:
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

    def google_search(self, address="") -> None:
        """
        Gets potentially useful information from Google.
        """
        if not address:
            address = self.address
        try:
            params = {'cx': self.google_custom_engine_id, 'q': address, 'key': self.google_custom_search_api_key}
            req = requests.get("https://customsearch.googleapis.com/customsearch/v1", params=params)
            # If the response was successful, no Exception will be raised
            req.raise_for_status()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:
            print('Success!')

            content = req.json()
            search_info = content['searchInformation']
            print(f"Total results: {search_info['totalResults']}")
            if int(search_info['totalResults']) > 0:
                relevant_results = []
                for elt in content['items']:
                    for keyword in self.google_keywords:
                        if keyword in elt['title'] or keyword in elt['link']:
                            relevant_results.append(elt)
                            break

                print(f"Relevant results:\n" + '\n'.join(f"{elt['title'], elt['link']}" for elt in relevant_results))
            else:
                print("No results found.")

    def twitter_search(self, address="") -> None:
        """
        Gets potentially useful information from Twitter
        :return: None
        """
        if not address:
            address = self.address

        query = f"{address} lang:en -is:retweet -is:reply -is:quote"
        tweet_fields = "text,author_id,created_at,source"
        try:
            headers = {"Authorization": f"Bearer {self.twitter_bearer_token}"}
            params = {'query': query, 'tweet.fields': {tweet_fields}, 'max_results': 10}

            response = requests.get("https://api.twitter.com/2/tweets/search/recent", headers=headers, params=params)

            # To get user's username from its ID
            # response2 = requests.get("https://api.twitter.com/2/users/1451510344329965570", headers=headers)

        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')  # Python 3.6
        except Exception as err:
            print(f'Other error occurred: {err}')  # Python 3.6

        else:
            print("Success!")
            print(json.dumps(response.json(), indent=4, sort_keys=True))

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
        while not token_req and counter < 100:
            try:
                counter += 1
                response = requests.post('https://www.reddit.com/api/v1/access_token',
                                         auth=auth, data=data, headers=headers)
                access_token = response.json()['access_token']
            except KeyError:
                pass
            else:
                token_req = True
        return access_token

    def reddit_search(self, address="") -> None:
        """
        Gets potentially useful information from Reddit
        :return: None
        """
        if not address:
            address = self.address

        if not self.reddit_access_token:
            print(f"Could not retrieve any information from Reddit, invalid access token! (={self.reddit_access_token})")
            return

        # add authorization to our headers dictionary
        headers = {'User-Agent': 'BTC_Tracker/0.0.1', 'Authorization': f"bearer {self.reddit_access_token}"}
        requests.get('https://oauth.reddit.com/api/v1/me', headers=headers)

        try:
            req = requests.get(f"https://oauth.reddit.com/search?q={address}",
                               headers=headers)

            req.raise_for_status()
        except HTTPError as http_err:
            if req.status_code == 401:  # If the token is not valid anymore, we request a new one
                self.reddit_access_token = self.get_reddit_token()
                self.reddit_search()    # And we start the search again
            else:
                print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')
        else:  # In case of success
            print("Success!")
            print(json.dumps(req.json(), indent=4, sort_keys=True))
