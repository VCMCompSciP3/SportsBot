import os
from alpaca_trade_api.rest import REST

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = "https://paper-api.alpaca.markets"

api = REST(API_KEY, API_SECRET, BASE_URL)

#Stock Ranking and BST Algorithm
class BSTNode:
    def __init__(self, score, symbol):
        self.score = score
        self.symbol = symbol
        self.left = None
        self.right = None

def insert_bst(root, score, symbol):
    if root is None:
        return BSTNode(score, symbol)
    if score < root.score:
        root.left = insert_bst(root.left, score, symbol)
    else:
        root.right = insert_bst(root.right, score, symbol)
    return root

def find_min(root):
    while root.left is not None:
        root = root.left
    return root.symbol

def find_max(root):
    while root.right is not None:
        root = root.right
    return root.symbol


