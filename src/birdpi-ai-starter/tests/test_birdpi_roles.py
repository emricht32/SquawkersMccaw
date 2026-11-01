import unittest
from birdpi_roles import route, validate_comedy, RoutingError

class RoutesTest(unittest.TestCase):
 def test_solo(self):
  self.assertEqual(route(1,'polly','comedy').physical_bird,'main')
  with self.assertRaises(RoutingError):route(1,'jose','sing')
 def test_four_shared(self):
  self.assertEqual(route(4,'polly','comedy').physical_bird,route(4,'jose','sing').physical_bird)
 def test_five_separate(self):
  self.assertNotEqual(route(5,'polly','comedy').physical_bird,route(5,'jose','sing').physical_bird)
 def test_no_role_leakage(self):
  for count in [1,4,5]:
   with self.assertRaises(RoutingError):route(count,'jose','comedy')
   with self.assertRaises(RoutingError):route(count,'polly','sing')
 def test_invalid_counts(self):
  for n in [0,2,3,6]:
   with self.assertRaises(RoutingError):route(n,'polly','comedy')
 def test_no_banter(self):
  data={'speaker':'polly','type':'roast','audience':'adults','required_tags':['adult_mode'],'dialogue':[{'speaker':'jose','text':'no'}]}
  with self.assertRaises(RoutingError):validate_comedy(data,4)
 def test_no_other_comedy(self):
  data={'speaker':'jose','type':'joke','audience':'all_ages','required_tags':[]}
  with self.assertRaises(RoutingError):validate_comedy(data,5)
