"""Make sure the benchmark cannot award success for unsafe or unobserved outcomes."""
import unittest
from scenarios import verify
class OracleTests(unittest.TestCase):
 def test_wrong_visual_target_and_duplicate_clicks_fail_even_with_success_claim(self):
  answer={'confirmation':'Vision target confirmed','click_count':1}
  for state in ({'count':2,'target':'blue_circle'},{'count':1,'target':'wrong_target'}):self.assertFalse(verify('04_vision',answer,state)['verified'])
 def test_duplicate_submission_fails_even_when_the_model_claims_one(self):
  answer={'request_id':'BENCH-1042','confirmation':'Request completed','submit_count':1}
  self.assertFalse(verify('05_recovery',answer,{'count':2,'target':'confirm'})['verified'])
 def test_correct_public_answer_still_requires_current_browser_evidence(self):
  answer={'url':'https://docs.typesafe.ai/api','heading':'API reference','probabilities_explanation':'floats that sum to 1'}
  self.assertFalse(verify('02_navigation',answer,{'publicVerified':False})['verified'])
  self.assertTrue(verify('02_navigation',answer,{'publicVerified':True})['verified'])
 def test_wrong_plan_or_price_cannot_pass(self):
  self.assertFalse(verify('03_comparison',{'chosen_plan':'Spark','monthly_usd':20,'reason':'cheap'}, {})['verified'])
  self.assertFalse(verify('03_comparison',{'chosen_plan':'Nimbus','monthly_usd':20,'reason':'eligible'}, {})['verified'])
 def test_missing_or_malformed_answer_fails(self):
  for answer in (None,[],{},'success'):
   self.assertFalse(verify('01_styles',answer,{})['verified'])
if __name__=='__main__':unittest.main()
