import unittest
from specialist_review import review, ROLES
def report():
    return {"schema":"osixbay.gple.f01.generated-biome-hypotheses.v1",
            "top_proposal":{"id":"candidate1","biome_mix":[0.4,0.35,0.25],
                            "hazard":0.1,"regrowth":0.12,"food_capacity":3.0}}
class SpecialistReviewTests(unittest.TestCase):
    def test_six_roles(self):
        out=review(report())
        self.assertEqual(set(out["reviewers"]),set(ROLES))
        self.assertFalse(out["approved_for_godot"])
    def test_bad_schema(self):
        x=report();x["schema"]="unknown"
        with self.assertRaises(ValueError):review(x)
    def test_fraction_guard(self):
        x=report();x["top_proposal"]["biome_mix"]=[1,1,1]
        with self.assertRaises(ValueError):review(x)
if __name__=="__main__":unittest.main()
