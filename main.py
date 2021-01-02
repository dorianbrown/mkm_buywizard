#!/usr/bin/env python

from pymkmapi import PyMkmApi
import argparse
import re
import numpy as np
from tqdm import tqdm


parser = argparse.ArgumentParser(description='Buylist optimizer for Magic Card Market')
parser.add_argument("--input", "-i", required=True, help="The filename with the list of desired cards")
args = parser.parse_args()


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


def extract_price_matrix(cardlist, api, search_params):
    for card in tqdm(cardlist, unit="card"):
        product = api.find_product(card, exact=True)[0]
        articlelist = api.get_articles(product["idProduct"], **search_params)
        # Filter by country
        articlelist = [a for a in articlelist if a['seller']['address']['country'] in search_params["countries"]]
        # Take lowest price per seller
        all_sellers = [a['seller']['idUser'] for a in articlelist]
        unique_sellers = [x for x in set(all_sellers)]
        articlelist = [articlelist[all_sellers.index(seller)] for seller in unique_sellers]

        if "price_mat" not in locals():
            price_mat = [[a['price'] for a in articlelist]]
            seller_idx = [a['seller']['idUser'] for a in articlelist]
        else:
            # Add empty row for new card
            price_mat.append([np.inf] * len(price_mat[-1]))
            for article in articlelist:
                seller = article['seller']['idUser']
                if seller not in seller_idx:
                    price_mat[-1].append(article['price'])
                    seller_idx.append(seller)
                else:
                    price_mat[-1][seller_idx.index(seller)] = article['price']
    # Post processing of price matrix
    price_mat = np.array([row + [np.inf] * (len(price_mat[-1]) - len(row)) for row in price_mat])
    return price_mat, seller_idx


def main():
    api = PyMkmApi()

    cardlist = load_cardlist(args.input)
    api.logger.info(f"Loaded list of {len(cardlist)} cards")

    price_mat, seller_idx = extract_price_matrix(cardlist, api, api.config["search_filters"])

    # Remove cards without valid sellers
    no_matches, *_ = np.where(price_mat.min(axis=1) == np.inf)
    for ind in no_matches[::-1]:
        api.logger.warning(f"No sellers found in search parameters for [{cardlist[ind]}]. Removing from optimization")
        price_mat = np.delete(price_mat, ind, axis=0)

    return None


if __name__ == '__main__':
    main()
