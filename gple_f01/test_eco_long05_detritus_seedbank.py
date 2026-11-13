"""ECO-LONG-05 invariants: parent-paid bank, recycling, no resurrection."""
import math
import unittest
from f01_feeding_bridge_p0 import F01Feeding
from long05_detritus_seedbank_audit import seedbank_from_live_parents,apply_extra_mineralization,advance

class EcoLong05Tests(unittest.TestCase):
    def test_seedbank_conserves_biomass_and_gene_provenance(self):
        sim=F01Feeding(seed=11)
        initial=sim.eco.world.total_biomass()
        records=seedbank_from_live_parents(sim)
        self.assertEqual(len(records),6)
        self.assertEqual(len(sim.eco.world.seeds),6)
        self.assertAlmostEqual(sim.eco.world.total_biomass(),initial,places=8)
        for record in records:
            parent=next(x for x in sim.eco.world.genetic.life.individuals if x.identity==record["parent_id"])
            seed=next(x for x in sim.eco.world.seeds if x.identity==record["seed_id"])
            self.assertEqual(parent.species,seed.species)
            self.assertGreater(seed.biomass,0)
        sim.audit()
    def test_bank_cannot_be_created_twice_or_after_tick(self):
        sim=F01Feeding()
        seedbank_from_live_parents(sim)
        with self.assertRaises(ValueError):seedbank_from_live_parents(sim)
        sim2=F01Feeding();sim2.tick()
        with self.assertRaises(ValueError):seedbank_from_live_parents(sim2)
    def test_recycling_is_one_way_conservative_and_capped(self):
        sim=F01Feeding()
        net=sim.eco.world.genetic.life.hydro.network
        before=sim.eco.world.total_biomass()
        source=sum(web.state.detritus for web in net.nodes.values())
        nutrients=sum(web.state.nutrients for web in net.nodes.values())
        flux=apply_extra_mineralization(sim)
        self.assertGreater(flux,0)
        self.assertAlmostEqual(sum(web.state.detritus for web in net.nodes.values()),source-flux,places=7)
        self.assertAlmostEqual(sum(web.state.nutrients for web in net.nodes.values()),nutrients+flux,places=7)
        self.assertAlmostEqual(sim.eco.world.total_biomass(),before,places=7)
    def test_replay_restores_genetic_seedbank_and_counters(self):
        a=F01Feeding(seed=23);seedbank_from_live_parents(a)
        for _ in range(70):advance(a,boosted=True)
        b=F01Feeding.restore(a.snapshot())
        for _ in range(60):
            advance(a,boosted=True);advance(b,boosted=True)
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_expired_seeds_not_respawned(self):
        sim=F01Feeding(seed=37);seedbank_from_live_parents(sim)
        for _ in range(250):advance(sim,boosted=True)
        sim.audit()
        # Once both living parents and paid seeds are gone, no source of new individuals remains.
        if not sim.eco.world.genetic.life.individuals and not sim.eco.world.seeds:
            for _ in range(30):
                advance(sim,boosted=True)
                self.assertEqual(len(sim.eco.world.genetic.life.individuals),0)
                self.assertEqual(len(sim.eco.world.seeds),0)

if __name__=="__main__":
    unittest.main()
