from nlp.taxonomy import OCCASION_ADJACENCY
from nlp.preferences import canonical
def score_occasion(user_occasion, product_primary, product_secondary=None):
    if not user_occasion: return 0.0
    wanted=canonical("occasion",user_occasion)
    tags={canonical("occasion",v) for v in [product_primary]+list(product_secondary or []) if v}
    if wanted in tags: return 10.0
    return 5.0 if tags & OCCASION_ADJACENCY.get(wanted,set()) else 0.0
