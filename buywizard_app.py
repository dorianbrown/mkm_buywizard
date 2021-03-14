#!/usr/bin/env python3
"""
The PyMKM example app.
"""

__author__ = "Andreas Ehrlund"
__version__ = "2.5.0"
__license__ = "MIT"

import json
import logging
import logging.handlers
import sys

from pprint import pprint as pp
import numpy as np
import pandas as pd

from pymkmapi import PyMkmApi, CardmarketError


class BuywizardApp:
    logger = None

    def __init__(self, config=None):

        # Setup Logging
        self.logger = logging.getLogger(__name__)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh = logging.handlers.RotatingFileHandler(
            f"log_pymkm.log", maxBytes=500000, backupCount=2
        )
        fh.setLevel(logging.WARNING)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setLevel(logging.ERROR)  # This gets outputted to stdout
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)

        self.logger.debug(">> Loading config file")
        try:
            with open("config.json", "r") as config_file:
                self.config = json.load(config_file)
        except FileNotFoundError:
            self.logger.error(
                "You must copy config_template.json to config.json and populate the fields."
            )
            sys.exit(0)

        fh.setLevel(self.config["log_level"])
        self.logger.setLevel(self.config["log_level"])
        self.api = PyMkmApi(config=self.config)
        print("Fetching Cardmarket account data...")
        self.account = self.get_account_data()
        self.wantlists = self.api.get_wantslists()

    def start(self, args=None):

        print(f"\nLogged in as: {self.account['name']['firstName']} {self.account['name']['lastName']} ({self.account['username']})")

        # print("\nWhich wantlist would you like to optimize?\n")
        # for i, list in enumerate(self.wantlists):
        #     print(f"\t[{i}]: {list['name']} ({list['itemCount']} cards)")
        # choice = int(input("\nEnter your choice: "))
        # os.system("clear")
        #
        # self.optimize_wantlist(choice)

        self.optimize_wantlist(0)

    def get_account_data(self):
        return self.api.get_account()["account"]

    def async_get_retry(self, item_type, item_id_list, **kwargs):
        print(f"Async fetching: {item_type}")

        ret_list = [None]*len(item_id_list)
        to_find = item_id_list.copy()

        round = 1
        while len([x for x in ret_list if x is not None]) < len(item_id_list):
            print(f"Fetch round {round}: {len(to_find)} items left")
            round += 1
            results = self.api.get_items_async(
                item_type=item_type,
                item_id_list=to_find,
                **kwargs
            )

            for ind in range(len(ret_list)):
                if (ret_list[ind] is None) and (len(results) > 0):
                    ret_list[ind] = results.pop(0)
                    if ret_list[ind] is not None:
                        to_find.pop(0)

        return ret_list

    def get_wantlist_data(self, wantlist_id):
        want_items = self.api.get_wantslist_items(self.wantlists[wantlist_id]['idWantsList']).get('item')

        products = [x for x in want_items if x['type'] == 'product']
        metaprod_wants = [x for x in want_items if x['type'] == 'metaproduct']

        metaproducts = self.async_get_retry("metaproducts", [x['idMetaproduct'] for x in metaprod_wants])

        product_ids = [prod['idProduct'] for prod in products]

        for metaprod in metaproducts:
            for prod in metaprod['product']:
                product_ids.append(prod['idProduct'])

        articles = self.async_get_retry("articles", product_ids, **self.config['search_filters'])

        # Filter down to countries
        for i in range(len(articles)):
            for j, item in reversed(list(enumerate(articles[i]['article']))):
                if item['seller']['address']['country'] not in self.config['search_filters']['countries']:
                    del articles[i]['article'][j]

        # Output formatting
        prod_to_metaprod = {}
        for metaprod in metaproducts:
            for prod in metaprod['product']:
                prod_to_metaprod[prod['idProduct']] = prod['idMetaproduct']

        lod = []
        for ind, prod_id in enumerate(product_ids):
            seller_prices = {art['seller']['idUser']: art['price'] for art in articles[ind]['article']}
            lod.append({
                "prod_id": prod_id,
                **seller_prices
            })
            if prod_id in prod_to_metaprod.keys():
                lod[-1]['metaprod_id'] = prod_to_metaprod[prod_id]

        # TODO: Create article_id dataframe (for translation back to article_id list)
        price_df = pd.DataFrame(lod).set_index(['metaprod_id', 'prod_id']).fillna(np.inf)

        zero_rows, *_ = np.where((price_df < np.inf).sum(axis=1) == 0)
        if len(zero_rows) > 0:
            print(f"There were {len(zero_rows)} cards with 0 sellers matching your search preferences."
                  f"We are removing:")
        price_df = price_df[~((price_df < np.inf).sum(axis=1) == 0)]

        return price_df

    def optimize_wantlist(self, wantlist_id):

        # TODO Filter items out using wantlist preferences
        price_df = self.get_wantlist_data(wantlist_id)


        pass
