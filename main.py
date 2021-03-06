#!/usr/bin/env python

from pymkmapi import PyMkmApi
import argparse
import re
import numpy as np
from pprint import pprint
from tqdm import tqdm


# TODO: Dynamically calculate shipping costs for [country -> NL] pairs.
#  We only have to do this once, and cache it as a local file.
# TODO: See if we can replace the find_product and get_articles with get_item_async
# TODO: Get productId that's the cheapest (currently most frequent)
# TODO: Implement retries on timeouts


class Batching:
    def __init__(self, batch_indices, price_matrix):
        self.batch_indices = batch_indices
        self.price_matrix = price_matrix

    def __repr__(self):
        return f"batch({self.batch_indices})"

    def total_cost(self, separate=False):
        prices = [self.price_matrix[i, self.batch_indices[i]] for i in range(len(self.batch_indices))]
        shipping = [calc_shipping_cost(cnt) for cnt in self.batch_counts[1]]

        if separate:
            return sum(prices), sum(shipping)
        return sum(prices) + sum(shipping)

    def change_seller(self, card_ind, seller_ind):
        self.batch_indices[card_ind] = seller_ind

    # @property

    @property
    def batch_counts(self):
        seller_idx, size = np.unique(self.batch_indices, return_counts=True)
        return seller_idx, size


def load_cardlist(fn):
    """
    Using given filename, loads and parses the card names in the file and returns them in a list
    :param fn: string
    :return: list[string]
    """
    with open(fn, 'r') as f:
        lines = f.readlines()
    lines = [line.strip() for line in lines if line.strip() != ""]
    if fn.endswith(".md"):
        retlist = [re.findall(r"^.+\[([^\]]+)\]", line)[0] for line in lines]
    else:
        retlist = [line.strip() for line in lines]
    return retlist


def extract_mostfreq_product(products):
    # TODO: Prefer standard sets (non-duel crap).
    mostfreq_ind = np.argmax([prod['countArticles'] if prod['countArticles'] else 0 for prod in products])
    return products[mostfreq_ind]


def calc_shipping_cost(n):
    if n == 0:
        return 0
    elif n <= 4:
        return 1.26
    elif n <= 17:
        return 2.22
    elif n <= 40:
        return 3.38


def extract_price_matrix(cardlist, api, search_params):
    # TODO: Make find_product async
    productlist = [api.find_product(card, exact=True) for card in tqdm(cardlist)]
    productlist = [extract_mostfreq_product(prod) for prod in productlist]
    # articlelist = [api.get_articles(prod['idProduct'], **search_params) for prod in tqdm(productlist)]
    articlelist = api.get_items_async("articles", [p['idProduct'] for p in productlist], **search_params)
    for articles in articlelist:
        # Filter by country
        articles = [a for a in articles['article'] if a['seller']['address']['country'] in search_params["countries"]]
        # Take lowest price per seller
        all_sellers = [a['seller']['idUser'] for a in articles]
        unique_sellers = [x for x in set(all_sellers)]
        articles = [articles[all_sellers.index(seller)] for seller in unique_sellers]

        if "price_mat" not in locals():
            price_mat = [[a['price'] for a in articles]]
            seller_idx = [a['seller']['idUser'] for a in articles]
        else:
            # Add empty row for new card
            price_mat.append([np.inf] * len(price_mat[-1]))
            for article in articles:
                seller = article['seller']['idUser']
                if seller not in seller_idx:
                    price_mat[-1].append(article['price'])
                    seller_idx.append(seller)
                else:
                    price_mat[-1][seller_idx.index(seller)] = article['price']
    # Post processing of price matrix
    price_mat = np.array([row + [np.inf] * (len(price_mat[-1]) - len(row)) for row in price_mat])

    # Remove cards without valid sellers
    no_matches, *_ = np.where(price_mat.min(axis=1) == np.inf)
    for ind in no_matches[::-1]:
        api.logger.warning(f"No sellers found in search parameters for [{cardlist[ind]}]. Removing from optimization")
        price_mat = np.delete(price_mat, ind, axis=0)

    return price_mat, seller_idx


def main():

    parser = argparse.ArgumentParser(description='Buylist optimizer for Magic Card Market')
    parser.add_argument("--input", "-i", required=True, help="The filename with the list of desired cards")
    args = parser.parse_args()

    api = PyMkmApi()

    cardlist = load_cardlist(args.input)
    pprint(cardlist)
    api.logger.info(f"Loaded list of {len(cardlist)} cards")

    price_mat, seller_idx = extract_price_matrix(cardlist, api, api.config["search_filters"])

    pprint(list(zip(cardlist, price_mat.min(axis=1))))

    return None


if __name__ == '__main__':
    main()
