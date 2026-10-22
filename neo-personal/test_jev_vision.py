"""Jev grounding contracts, refusal boundaries and transport; no paid inference."""
import io
import json
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from browserhelm import BrowserHelmGateway
from vision import VisionProvider, TYPESAFE_ENDPOINT, JEV_VISION_MODEL, visual_act
import test_vision
from test_vision import IMAGE, image_png

CONFIG = {'enabled': True, 'provider': 'typesafe', 'endpoint': TYPESAFE_ENDPOINT,
          'model': JEV_VISION_MODEL, 'minConfidence': 0.9}


def response(probability=0.99, confidence=0.98):
    return {'model': JEV_VISION_MODEL, 'answers': {
        'unique_target': {'type': 'noul', 'noul': probability},
        'target_box': {'type': 'box', 'confidence': confidence,
                       'box': {'left': 0.2, 'right': 0.6, 'top': 0.3, 'bottom': 0.7}}},
        'usage': {'input_tokens': 321, 'output_tokens': 24}}


class JevVisionTests(unittest.TestCase):
    def test_only_explicit_fixed_origin_pinned_model_and_valid_threshold(self):
        for endpoint in ['http://api.typesafe.ai/v1', TYPESAFE_ENDPOINT+'?key=x',
                         TYPESAFE_ENDPOINT+'.evil.test', 'https://key@api.typesafe.ai/v1', 'http://127.0.0.1:1234/v1']:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                VisionProvider({**CONFIG, 'endpoint': endpoint}, 'fake')
        for model in ['jev-latest', 'jev-preview', 'jev-1.13.0', '', 'other']:
            with self.subTest(model=model), self.assertRaises(ValueError):
                VisionProvider({**CONFIG, 'model': model}, 'fake')
        for threshold in [True, None, '0.9', -1, 0.49, 1.01, float('nan'), float('inf')]:
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                VisionProvider({**CONFIG, 'minConfidence': threshold}, 'fake')
        with self.assertRaises(ValueError): VisionProvider(CONFIG, 'fake\nkey')

    def test_single_request_shares_image_and_asks_unique_presence_plus_box(self):
        provider = VisionProvider(CONFIG, 'fake')
        with patch.object(provider, 'request', return_value=response()) as request, patch.object(provider, 'test') as test:
            result = provider.point(IMAGE, 'The green triangle')
        test.assert_not_called(); request.assert_called_once()
        path, payload = request.call_args.args
        self.assertEqual(path, '/systemone')
        self.assertEqual(payload['model'], JEV_VISION_MODEL)
        self.assertEqual(len(payload['assets']), 1)
        ref = payload['state']['screenshot']
        self.assertEqual(payload['assets'][ref]['data_base64'], IMAGE)
        self.assertEqual(payload['questions']['target_box']['type'], 'box')
        self.assertIn('exactly one', payload['questions']['unique_target']['instructions'])
        self.assertTrue(result['found']); self.assertEqual((result['x'], result['y']), (400, 500))
        self.assertEqual(result['usage'], {'input_tokens': 321, 'output_tokens': 24})
        self.assertNotIn(IMAGE, json.dumps(result)); self.assertNotIn('fake', json.dumps(result))

    def test_absent_ambiguous_and_low_confidence_ignore_even_valid_box(self):
        provider = VisionProvider(CONFIG, 'fake')
        for probability, confidence in [(0.01, 0.99), (0.89, 1), (1, 0.89), (0.1, 0.1)]:
            with self.subTest(probability=probability, confidence=confidence), patch.object(provider, 'request', return_value=response(probability, confidence)):
                result = provider.point(IMAGE, 'Absent or ambiguous target')
            self.assertFalse(result['found']); self.assertEqual((result['x'], result['y']), (0, 0))
            self.assertIsNone(result['box'])
        with patch.object(provider, 'request', return_value=response(0.9, 0.9)):
            self.assertTrue(provider.point(IMAGE, 'Target')['found'])

    def test_malformed_evidence_never_becomes_a_point(self):
        values = []
        for field, bad in [('noul', True), ('noul', float('nan')), ('noul', 2), ('type', 'choice')]:
            raw=response(); raw['answers']['unique_target'][field]=bad; values.append(raw)
        for bad in [None, True, '0.99', -1, float('inf')]:
            raw=response(); raw['answers']['target_box']['confidence']=bad; values.append(raw)
        for box in [None, {}, {'left': 0, 'right': 1, 'top': 0, 'bottom': 1, 'extra': 2},
                    {'left': 0.8, 'right': 0.2, 'top': 0, 'bottom': 1},
                    {'left': 0, 'right': 1, 'top': True, 'bottom': 1},
                    {'left': -0.1, 'right': 1, 'top': 0, 'bottom': 1}]:
            raw=response(); raw['answers']['target_box']['box']=box; values.append(raw)
        values += [{}, {'model': JEV_VISION_MODEL, 'answers': None}, {**response(), 'model': 'jev-latest'}]
        provider=VisionProvider(CONFIG, 'fake')
        for raw in values:
            with self.subTest(raw=raw), patch.object(provider, 'request', return_value=raw), self.assertRaises(ValueError):
                provider.point(IMAGE, 'Target')

    def test_small_and_large_images_rejected_before_upload(self):
        provider=VisionProvider(CONFIG, 'fake')
        for image in [image_png(256,256), image_png(1600,800), image_png(1000,200)]:
            with patch.object(provider, 'request') as request, self.assertRaises(ValueError):
                provider.point(image, 'Target')
            request.assert_not_called()

    def test_connection_test_is_get_only_and_not_an_image_capability_claim(self):
        provider=VisionProvider(CONFIG, 'fake')
        with patch.object(provider, 'request', return_value={'models': [{'name':'jev-latest'}]}) as request:
            self.assertTrue(provider.test()['connected'])
        request.assert_called_once_with('/models', timeout=10)
        for metadata in [{}, {'models':None}, {'models':[]}]:
            with patch.object(provider, 'request', return_value=metadata), self.assertRaises(ValueError): provider.test()
        provider=VisionProvider(CONFIG)
        with patch.object(provider.opener, 'open') as request, self.assertRaises(ValueError): provider.test()
        request.assert_not_called()

    def test_transport_enables_images_only_for_inference_and_never_leaks_or_retries(self):
        provider=VisionProvider(CONFIG, 'fake')
        for path in ['/systemone', '/models']:
            error=urllib.error.HTTPError(TYPESAFE_ENDPOINT, 529, 'private', {}, io.BytesIO(b'screenshot-secret'))
            with patch.object(provider.opener, 'open', side_effect=error) as request, self.assertRaises(ValueError) as caught:
                provider.request(path, {} if path == '/systemone' else None)
            request.assert_called_once(); req=request.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'), 'Bearer fake')
            self.assertEqual(req.get_header('Typesafe-danger-zone-images'), 'true' if path == '/systemone' else None)
            self.assertNotIn('secret', str(caught.exception)); self.assertNotIn('private', str(caught.exception))
            error.close()

    def test_usage_is_reported_without_inventing_cost_or_missing_tokens(self):
        provider=VisionProvider(CONFIG, 'fake')
        for usage, expected in [(None, {}), ({'input_tokens':True, 'output_tokens':-1}, {}),
                                ({'input_tokens':12, 'cost':0.01}, {'input_tokens':12})]:
            with patch.object(provider, 'request', return_value={**response(), 'usage':usage}):
                self.assertEqual(provider.point(IMAGE, 'Target')['usage'], expected)

    def test_vision_key_cache_never_crosses_cloud_providers(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway=BrowserHelmGateway({'vision':CONFIG},folder)
            try:
                with patch.object(gateway,'read_provider_key',side_effect=['fake-jev','fake-router','fake-jev']) as read:
                    self.assertEqual(gateway.vision_key('typesafe'),'fake-jev')
                    self.assertEqual(gateway.vision_key('typesafe'),'fake-jev')
                    self.assertEqual(gateway.vision_key('openrouter'),'fake-router')
                    self.assertEqual(gateway.vision_key('typesafe'),'fake-jev')
                self.assertEqual([c.args[0] for c in read.call_args_list],['typesafe','openrouter','typesafe'])
            finally: gateway.artifacts.cleanup(); gateway.moves_pool.shutdown()


class JevVisualActionTests(test_vision.VisualActionTests):
    # Re-run every existing freshness, cancellation, click and learning boundary.
    def setUp(self):
        super().setUp()
        self.g.settings['vision']=dict(CONFIG)
        self.g.vision_api_key='fake-jev'

    def test_absent_target_never_dispatches_click_and_counts_native_tokens(self):
        self.g.context.row={'provider_calls':0,'provider_tokens':0,'provider_unknown':0}
        with patch.object(self.g,'run_browser',return_value=self.viewport) as run, patch.object(self.g,'upstream_call',return_value=self.screen), patch('vision.VisionProvider.request',return_value=response(0.01,0.99)):
            report=visual_act(self.g,self.args,1)
        self.assertFalse(report['clicked']); self.assertFalse(report['found']); run.assert_called_once()
        self.assertEqual(self.g.context.row['provider_tokens'],345)
        self.assertEqual(self.g.context.row['provider_calls'],1)
        self.assertEqual(self.g.context.row['provider_unknown'],0)

    def test_provider_failure_never_dispatches_click(self):
        with patch.object(self.g,'run_browser',return_value=self.viewport) as run, patch.object(self.g,'upstream_call',return_value=self.screen), patch('vision.VisionProvider.request',side_effect=ValueError('HTTP 529')):
            with self.assertRaises(ValueError): visual_act(self.g,self.args,1)
        run.assert_called_once()


class JevLearningTests(test_vision.VisualLearningTests):
    def setUp(self):
        super().setUp()
        self.g.settings['vision'] = dict(CONFIG)
        self.g.vision_api_key = 'fake-jev'

    def test_raising_threshold_cannot_reuse_previously_accepted_coordinates(self):
        self.attempt(); self.attempt()
        self.assertEqual(self.attempt()[1], 0)
        self.g.settings['vision']['minConfidence'] = 0.95
        self.assertEqual(self.attempt()[1], 1)

    def test_scene_instruction_postcondition_model_and_account_are_isolated(self):
        self.attempt(); self.attempt()
        self.g.settings['vision'] = {**test_vision.DEFAULT_VISION, 'enabled': True}
        self.assertEqual(self.attempt()[1], 1)

    def test_explicit_default_threshold_matches_omitted_default(self):
        self.g.settings['vision'].pop('minConfidence')
        self.attempt(); self.attempt()
        self.g.settings['vision']['minConfidence'] = 0.9
        self.assertEqual(self.attempt()[1], 0)


if __name__ == '__main__': unittest.main()
