import unittest
from copy import deepcopy
from world25d import (validate_25d_export,navigable,position_world,
                      validate_step,visual_frame,choose_lod)

def fixture():
    def cell(playable=True,elevation=2.0,slope=2.0,water=0):
        return {"playable":playable,"biome":"alien_forest","suitable_for_f01":True,
                "traversable":True,"substrate":"soil","water_depth_m":water,
                "resources":{"biofilm":1},"resource_capacity":{"biofilm":2},
                "resource_regrowth":{"biofilm":0.1},"danger":0.1,"shelter":True,
                "temperature":19.5,"humidity":0.7,"elevation_m":elevation,
                "slope_deg":slope,"water_surface_y_m":elevation+water}
    return {"schema":"osixbay.genesis.gple.f01.habitat-export.v1",
            "zone_id":"SYNTHETIC_TEST_ONLY","world_version":"test1","source_scene":"TEST_FIXTURE",
            "source_commit":"TEST_FIXTURE","grid_resolution_m":2.0,
            "origin_world":[100.0,0.0,200.0],
            "coordinate_system":{"horizontal":["x","z"],"vertical":"y","units":"meters"},
            "camera_mode":"exploration","playable_boundary_source":"TEST_ONLY",
            "cells":[[cell(),cell(playable=False),cell()],
                     [cell(),cell(water=0.20),cell(slope=40.0)],
                     [cell(),cell(water=0.8),cell()]]}

def actor(x=0,z=0):
    return {"entity_id":"F01-1","species_id":"F01","cell_x":x,"cell_z":z,
            "action_state":"forage","lifecycle_stage":"adult"}

class World25DTests(unittest.TestCase):
    def test_valid_fixture(self):
        self.assertEqual(validate_25d_export(fixture())["viable_cells"],8)
    def test_real_world_origin(self):
        self.assertEqual(position_world(fixture(),0,0),[101.0,2.0,201.0])
    def test_irregular_mask(self):
        self.assertFalse(navigable(fixture(),1,0))
    def test_steep_slope_rejected(self):
        self.assertFalse(navigable(fixture(),2,1))
    def test_deep_water_rejected(self):
        self.assertFalse(navigable(fixture(),1,2))
    def test_no_diagonal_or_teleport(self):
        f=fixture()
        self.assertTrue(validate_step(f,(0,0),(0,1)))
        self.assertFalse(validate_step(f,(0,0),(1,1)))
        self.assertFalse(validate_step(f,(0,0),(2,2)))
    def test_lod_ranges(self):
        self.assertEqual([choose_lod(v) for v in (14,15,50,180)],
                         ["near","mid","far","culled"])
    def test_view_never_mutates_state(self):
        f=fixture(); a=[actor()]; orig=deepcopy((f,a))
        frame=visual_frame(f,a,camera_xyz=[101,3,201],mode="exploration",tick=4,world_version="test1")
        self.assertEqual((f,a),orig)
        self.assertFalse(frame["authoritative_simulation_mutated"])
        self.assertEqual(frame["entities"][0]["lod"],"near")
    def test_management_camera_requires_source_mode(self):
        f=fixture()
        with self.assertRaises(ValueError):
            visual_frame(f,[actor()],camera_xyz=[101,3,201],
                         mode="management",tick=4,world_version="test1")
        f["camera_mode"]="management"
        frame=visual_frame(f,[actor()],camera_xyz=[101,130,201],
                           mode="management",tick=4,world_version="test1")
        self.assertEqual(frame["entities"][0]["lod"],"far")
    def test_stale_version_rejected(self):
        with self.assertRaises(ValueError):
            visual_frame(fixture(),[actor()],camera_xyz=[101,3,201],
                         mode="exploration",tick=4,world_version="wrong")
    def test_unsupported_missing_elevation(self):
        f=fixture();del f["cells"][0][0]["elevation_m"]
        with self.assertRaises(ValueError):validate_25d_export(f)
    def test_bad_water_surface(self):
        f=fixture();f["cells"][1][1]["water_surface_y_m"]=1
        with self.assertRaises(ValueError):validate_25d_export(f)
    def test_duplicate_entity(self):
        with self.assertRaises(ValueError):
            visual_frame(fixture(),[actor(),actor()],camera_xyz=[101,3,201],
                         mode="exploration",tick=4,world_version="test1")
if __name__=="__main__":unittest.main()
