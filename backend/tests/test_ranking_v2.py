import unittest, copy, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nlp.rule_engine import rank_products, score_product, active_weights, POLICY
from nlp.preferences import canonical, check_hard_filters, attributes
from scoring.occasion import score_occasion

def product(sku="a",color="Navy Blue",fabric="Silk",rank=1):
    return {"sku_id":sku,"category":"dress","gender":"female","in_stock":True,"is_active":True,
            "sub_category":"Anarkali-Style Dress","specific_color":color,"fabric_category":fabric,
            "occasion_tags":["smart_casual","wedding_guest"],"retrieval_rank":rank,
            "variants":[{"sku":sku,"size":"M","price_minor":200000,"inventory_qty":5,"is_active":True,"stock_known":True}]}
def prefs():
    return {"gender":"female","category":"dress","size":"M","budget":{"max":3000},
            "requested_attributes":{"color":["navy blue"],"fabric":["silk"]},"must_have":{},"exclude":{}}

class RankingTests(unittest.TestCase):
    def test_complete_over_business(self):
        a=product();b=product("b","Wine Red","Velvet")
        b["business_evidence"]={"verified":True,"source":"sales","as_of":"2026-09-30","sales_score":1,"rating_score":1,"trend_score":1}
        policy=copy.deepcopy(POLICY);policy["business"]["enabled"]=True
        self.assertEqual(rank_products(prefs(),[b,a],policy=policy)[0]["sku_id"],"a")
    def test_missing_weights(self):
        self.assertEqual(active_weights({},POLICY)["relevance"],1)
        policy=copy.deepcopy(POLICY)
        policy["business"]["enabled"]=True;policy["personalization"]["body_enabled"]=True;policy["personalization"]["height_enabled"]=True
        self.assertAlmostEqual(active_weights({},policy)["relevance"],.95)
        self.assertAlmostEqual(active_weights({"body_type":"pear"},policy)["relevance"],.89)
        self.assertAlmostEqual(active_weights({"body_type":"pear","height_band":"petite"},policy)["relevance"],.85)
    def test_variant_stock_and_price(self):
        p=product();p["variants"] += [{"sku":"l","size":"L","price_minor":400000,"inventory_qty":0,"is_active":True}]
        q=prefs();q["size"]="L"
        self.assertFalse(check_hard_filters(p,q))
        p["variants"][1]["inventory_qty"]=5
        self.assertFalse(check_hard_filters(p,q))
        q["budget"]["max"]=4500
        self.assertTrue(check_hard_filters(p,q))
    def test_exclusions(self):
        q=prefs();q["exclude"]={"color":["blue"]}
        self.assertFalse(check_hard_filters(product(),q))
    def test_mandatory_unknown(self):
        q=prefs();q["must_have"]={"fabric":["cashmere"]}
        self.assertFalse(check_hard_filters(product(),q))
    def test_missing_product_attribute_not_rewarded(self):
        p=product();p["fabric_category"]=None
        s=score_product(prefs(),p)
        self.assertEqual(s["attribute_scores"]["fabric"],0)
        self.assertIn("fabric",s["unknown_attributes"])
    def test_secondary_occasion_exact(self):
        self.assertEqual(score_occasion("wedding_guest","smart_casual",["wedding_guest"]),10)
    def test_no_requested_features(self):
        q=prefs();q["requested_attributes"]={}
        a=product(rank=1);b=product("b",rank=8)
        self.assertGreater(score_product(q,a)["final_score"],score_product(q,b)["final_score"])
    def test_size_aliases(self):
        self.assertEqual(canonical("size","free size"),"FREE")
        self.assertNotEqual(canonical("size","3xl"),canonical("size","2xl"))
    def test_mens_excluded(self):
        p=product();p["gender"]="male"
        self.assertFalse(check_hard_filters(p,prefs()))

if __name__=="__main__":unittest.main()
