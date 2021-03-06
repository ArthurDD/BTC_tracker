## BTC Tracker tool



In order to use this tool, you will need to use different APIs:  
    
- BitcoinAbuse API
  - API key required (https://www.bitcoinabuse.com/api-docs)
  

- Google Custom Search API
  - Use of Programmable Search Engine: https://developers.google.com/custom-search/docs/overview
  - Doc for the PSE: https://developers.google.com/custom-search/v1/introduction
  - API doc: https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list


- Twitter API:
  - Request parameters: https://developer.twitter.com/en/docs/twitter-api/tweets/search/api-reference/get-tweets-search-all
  - Query Doc: https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query
  - Developer portal: https://developer.twitter.com/en/portal/register/keys
  - OAuth-2 doc for Twitter: https://developer.twitter.com/en/docs/authentication/oauth-2-0/application-only
  - Tutorial: https://towardsdatascience.com/searching-for-tweets-with-python-f659144b225f


### Credentials
Once every API has been configured, you will need to create your own _**credentials.json**_ file containing all the required keys to make the tool work.
To do so, you can simply copy/paste the following one and replace the **_##_** by your own credentials:

```json
{"bitcoinabuse": {
    "token": "##"
  },
  "google": {
    "custom_search_api_key": "##",
    "custom_engine_id":  "##"
    },
  "twitter": {
    "bearer_token": "##"
  }
 }
```
