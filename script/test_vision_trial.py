"""Independent shape oracles and the uninstalled UI-TARS action parser."""
import unittest
from jev_vision_smoke import inside_shape
from uitars_grounding_trial import parse_action


class ShapeOracleTests(unittest.TestCase):
    def test_correct_tile_is_not_enough_to_hit_its_shape(self):
        for case, inside, outside in [
            ('triangle',(400,170),(350,125)),
            ('circle',(150,170),(105,125)),
            ('square',(650,170),(570,170))]:
            with self.subTest(case=case):
                self.assertTrue(inside_shape(case,*inside))
                self.assertFalse(inside_shape(case,*outside))
        self.assertTrue(inside_shape('triangle',400,120))
        self.assertFalse(inside_shape('triangle',400,211))


class NativeTrialParserTests(unittest.TestCase):
    def test_one_literal_click_proposal_maps_native_pixels(self):
        self.assertEqual(parse_action("Action: click(start_box='(644,392)')",1288,784),
                         {'found':True,'x':500,'y':500})

    def test_explicit_refusals_never_supply_a_point(self):
        for reason in ['not_found','ambiguous']:
            self.assertEqual(parse_action("Action: finished(content='%s')"%reason,1288,784),
                             {'found':False,'x':0,'y':0})

    def test_unsupported_actions_code_and_coordinates_fail_closed(self):
        for value in [None,'',"Action: click(start_box='(1288,0)')",
                      "Action: click(start_box='(-1,0)')", "Action: type(content='x')",
                      "Action: click(start_box='(1.5,0)')", "Action: click(start_box='(1,2)');run()",
                      "Thought: plan\nAction: click(start_box='(1,2)')",
                      "Action: click(start_box='(1,2)')\nAction: click(start_box='(3,4)')"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_action(value,1288,784)


if __name__ == '__main__': unittest.main()
