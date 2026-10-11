"""OpenRouter vision boundaries: fake credentials and mocked network only."""
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from openragnar import OpenRagnarGateway
from vision import VisionProvider, OPENROUTER_ENDPOINT
import test_vision
from test_vision import IMAGE

CONFIG = {'enabled': True, 'provider': 'openrouter', 'endpoint': OPENROUTER_ENDPOINT, 'model': 'qwen/qwen3.8-flash'}


class CloudVisionTests(unittest.TestCase):
    def test_remote_mode_requires_explicit_provider_and_fixed_origin(self):
        for endpoint in ['http://openrouter.ai/api/v1', 'https://openrouter.ai.evil.test/api/v1',
                         OPENROUTER_ENDPOINT + '?key=x', 'https://key@openrouter.ai/api/v1', 'http://127.0.0.1:1234/v1']:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                VisionProvider({**CONFIG, 'endpoint': endpoint}, 'fake')
        for model in ['auto', '../x', 'author/model?key=x', 'author/model/extra', '']:
            with self.subTest(model=model), self.assertRaises(ValueError): VisionProvider({**CONFIG, 'model': model}, 'fake')
        provider = VisionProvider(CONFIG)
        with patch.object(provider.opener, 'open') as request, self.assertRaises(ValueError): provider.test()
        request.assert_not_called()

    def test_one_image_request_bounded_json_reasoning_and_usage(self):
        provider = VisionProvider(CONFIG, 'fake')
        raw = {'choices': [{'message': {'content': '{"found":true,"x":400,"y":500}'}}],
               'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120, 'cost': 0.0001, 'private': 'omit'}}
        with patch.object(provider, 'request', return_value=raw) as request, patch.object(provider, 'test') as test:
            result = provider.point(IMAGE, 'Locate green button')
        test.assert_not_called()
        request.assert_called_once()
        path, payload = request.call_args.args
        self.assertEqual(path, '/chat/completions')
        self.assertEqual(payload['max_tokens'], 80)
        self.assertFalse(payload['stream']); self.assertFalse(payload['reasoning']['enabled'])
        self.assertTrue(payload['provider']['require_parameters'])
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertEqual(payload['messages'][1]['content'][1]['image_url']['url'], 'data:image/png;base64,' + IMAGE)
        self.assertEqual(result['usage'], {k: v for k, v in raw['usage'].items() if k != 'private'})
        self.assertNotIn('fake', json.dumps(result)); self.assertNotIn(IMAGE, json.dumps(result))

    def test_auth_and_catalog_test_never_send_image_or_paid_post(self):
        provider = VisionProvider(CONFIG, 'fake')
        metadata = {'data': {'architecture': {'input_modalities': ['text', 'image']}, 'endpoints': [
            {'supported_parameters': ['response_format', 'max_tokens', 'reasoning']}]}}
        with patch.object(provider, 'request', side_effect=[{'data': {}}, metadata]) as request:
            result = provider.test()
        self.assertTrue(result['connected'])
        self.assertEqual(request.call_args_list[0].args, ('/key',))
        self.assertEqual(request.call_args_list[1].args, ('/models/qwen/qwen3.8-flash/endpoints',))
        for invalid in [{'data': {}}, {'data': {'architecture': {'input_modalities': ['image']}, 'endpoints': []}}]:
            with patch.object(provider, 'request', side_effect=[{}, invalid]), self.assertRaises(ValueError): provider.test()

    def test_transport_does_not_leak_error_body_or_retry(self):
        provider = VisionProvider(CONFIG, 'fake')
        for error in [urllib.error.HTTPError(OPENROUTER_ENDPOINT, 401, 'secret body', {}, io.BytesIO(b'private screenshot')),
                      urllib.error.URLError('secret endpoint')]:
            with patch.object(provider.opener, 'open', side_effect=error) as request:
                with self.assertRaises(ValueError) as caught: provider.request('/chat/completions', {})
            request.assert_called_once()
            self.assertNotIn('secret', str(caught.exception)); self.assertNotIn('private', str(caught.exception))
            req = request.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'), 'Bearer fake')
        local = VisionProvider({'provider': 'lmstudio', 'endpoint': 'http://127.0.0.1:1234/v1', 'model': 'local'}, 'fake')
        with patch.object(local.opener, 'open', side_effect=urllib.error.URLError('offline')) as request:
            with self.assertRaises(ValueError): local.request('/models')
        self.assertIsNone(request.call_args.args[0].get_header('Authorization'))

    def test_invalid_point_or_usage_stops_without_inventing_result(self):
        provider = VisionProvider(CONFIG, 'fake')
        for content in ['not json', '{"found":true,"x":1000,"y":2}', '{"found":true,"x":true,"y":2}']:
            with patch.object(provider, 'request', return_value={'choices': [{'message': {'content': content}}]}), self.assertRaises(ValueError):
                provider.point(IMAGE, 'Locate target')
        with patch.object(provider, 'request', return_value={'choices': [{'message': {'content': '{"found":false,"x":0,"y":0}'}}], 'usage': None}):
            self.assertEqual(provider.point(IMAGE, 'Locate target')['usage'], {})

    def test_saved_switch_refreshes_existing_session_and_keeps_decision_key(self):
        with tempfile.TemporaryDirectory() as folder:
            gateway = OpenRagnarGateway({'provider': 'typesafe', 'vision': CONFIG}, folder, 'fake-jev')
            path = pathlib.Path(folder) / 'settings.json'; gateway.settings_path = path
            try:
                path.write_text(json.dumps({'vision': CONFIG}))
                self.assertEqual(gateway.vision_config()['provider'], 'openrouter')
                with patch.object(gateway, 'read_provider_key', return_value='fake-router') as read:
                    self.assertEqual(gateway.vision_key(), 'fake-router'); gateway.vision_key()
                read.assert_called_once_with('openrouter')
                path.write_text(json.dumps({'vision': {**CONFIG, 'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434', 'model': 'local'}}))
                self.assertEqual(gateway.vision_config()['model'], 'local')
                self.assertIsNone(gateway.vision_api_key)
                self.assertEqual(gateway.api_key, 'fake-jev')
                path.write_text('broken')
                with self.assertRaises(ValueError): gateway.vision_config()
                path.unlink()
                with self.assertRaises(ValueError): gateway.vision_config()
            finally: gateway.artifacts.cleanup(); gateway.moves_pool.shutdown()

    def test_presets_are_unique_current_model_ids_and_primary_links(self):
        models = json.loads(pathlib.Path(__file__).with_name('vision-models.json').read_text())
        self.assertEqual(len(models), 3)
        self.assertEqual(len({m['id'] for m in models}), 3)
        for model in models:
            VisionProvider({**CONFIG, 'model': model['id']}, 'fake')
            self.assertEqual(model['url'], 'https://openrouter.ai/' + model['id'])


class CloudVisualActionTests(test_vision.VisualActionTests):
    # Re-run the existing click/staleness/learning boundary suite with cloud config.
    def setUp(self):
        super().setUp()
        self.g.settings['vision'] = dict(CONFIG)
        self.g.vision_api_key = 'fake-router'

    def test_failed_cloud_inference_does_not_dispatch_click(self):
        with patch.object(self.g, 'run_browser', return_value=self.viewport) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', side_effect=ValueError('OpenRouter returned HTTP 429')):
            with self.assertRaises(ValueError):
                from vision import visual_act
                visual_act(self.g, self.args, 1)
        run.assert_called_once()


if __name__ == '__main__': unittest.main()
