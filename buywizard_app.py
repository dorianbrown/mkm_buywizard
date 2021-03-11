#!/usr/bin/env python3
"""
The PyMKM example app.
"""

__author__ = "Andreas Ehrlund"
__version__ = "2.5.0"
__license__ = "MIT"

import csv
import json
import logging
import logging.handlers
import pprint
import uuid
import sys
import re
import pkg_resources

import progressbar
import requests
import tabulate as tb
import os

from pprint import pprint as pp
from importlib import import_module
from datetime import datetime
from distutils.util import strtobool
from pkg_resources import parse_version

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

        self.optimize_wantlist(4)

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
        print("fetching metaproducts")

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

        # TODO: Put this into a nice datastructure?

        return want_items, product_ids, articles

    def optimize_wantlist(self, wantlist_id):

        # TODO Filter items out using wantlist preferences
        want_items, product_ids, articles = self.get_wantlist_data(wantlist_id)

        pass
