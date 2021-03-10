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

        # self.optimize_wantlist(choice)

        self.optimize_wantlist(0)

    def get_account_data(self):
        return self.api.get_account()["account"]

    def get_wantlist_articles(self, wantlist_id):
        want_items = self.api.get_wantslist_items(self.wantlists[wantlist_id]['idWantsList']).get('item')

        products = [x for x in want_items if x['type'] == 'product']
        metaprod_wants = [x for x in want_items if x['type'] == 'metaproduct']
        print("fetching metaproducts")

        with progressbar.ProgressBar(max_value=len(metaprod_wants)) as bar:
            metaproducts = []
            while len(metaproducts) < len(metaprod_wants):
                found = self.api.get_items_async(
                    item_type="metaproducts",
                    item_id_list=[x['idMetaproduct'] for x in metaprod_wants],
                    progressbar=bar
                )
                # Ordering of list gets lost here
                metaproducts += [f for f in found if f is not None]

        product_ids = [prod['idProduct'] for prod in products]

        for metaprod in metaproducts:
            for prod in metaprod['product']:
                product_ids.append(prod['idProduct'])

        with progressbar.ProgressBar(max_value=len(product_ids)) as bar:
            products = self.api.get_items_async(
                item_type="articles",
                item_id_list=product_ids,
                progressbar=bar
            )

        return None

    def optimize_wantlist(self, wantlist_id):

        self.get_wantlist_articles(wantlist_id)

