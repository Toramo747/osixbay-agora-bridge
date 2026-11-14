"""ECO-LONG-09 funnel accounting and replay regression."""
import unittest
from long09_fertility_funnel_audit import audit_case,SCENARIOS
class FertilityFunnelTests(unittest.TestCase):
    def test_traced_generations_not_spontaneous(self):
        result,rows=audit_case(11,SCENARIOS[0],ticks=48)
        self.assertTrue(result["biomass_conserved"])
        self.assertTrue(result["water_conserved"])
        self.assertTrue(result["no_respawn"])
        self.assertEqual(result["original_founders"],6)
        self.assertEqual(result["paid_initial_propagules"],6)
        self.assertEqual(len(rows),4*6*4)
        for g in result["generations"]:
            self.assertLessEqual(g["reproduced"],g["matured"])
            self.assertLessEqual(g["matured"],g["known"])
            self.assertLessEqual(g["germinated"],g["known"])
    def test_deterministic_funnel(self):
        a,annual=audit_case(23,SCENARIOS[1],ticks=72)
        b,repeat=audit_case(23,SCENARIOS[1],ticks=72)
        self.assertEqual(a,b)
        self.assertEqual(annual,repeat)
    def test_real_parent_events_required(self):
        a,_=audit_case(11,SCENARIOS[-1],ticks=90)
        born=a["total_plant_birth_events"]
        self.assertEqual(sum(g["known"] for g in a["generations"]),born+12)
        self.assertGreaterEqual(sum(g["reproduced"] for g in a["generations"]),1)
    def test_habitat_group_integrity(self):
        a,_=audit_case(37,SCENARIOS[0],ticks=48)
        for group in a["habitats"]:
            self.assertIn(group["patch"],("forest","shore","rock"))
            self.assertIn(group["species"],("producer_a","producer_b"))
            self.assertLessEqual(group["reproduced"],group["matured"])
if __name__=="__main__":unittest.main()
