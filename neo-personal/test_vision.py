"""Grounding and action boundary tests; no actual model, network or browser."""
import base64
import json
import struct
import tempfile
import unittest
from unittest.mock import patch
from openragnar import OpenRagnarGateway
from vision import VisionProvider, local_endpoint, png_size, visual_act, DEFAULT_VISION

IMAGE = base64.b64encode(b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 1000, 800) + b'\0' * 9).decode()


class VisionTests(unittest.TestCase):
    def test_private_screenshots_cannot_use_remote_endpoints_or_cloud_models(self):
        for url in ['https://example.com', 'http://localhost:11434', 'http://127.0.0.1.evil.test', 'http://u:p@127.0.0.1', 'http://127.0.0.1?key=x']:
            with self.subTest(url=url), self.assertRaises(ValueError): local_endpoint(url)
        self.assertEqual(local_endpoint('http://[::1]:11434/'), 'http://[::1]:11434')
        with self.assertRaises(ValueError): VisionProvider({**DEFAULT_VISION, 'model': 'qwen3-vl:235b-cloud'})
        provider = VisionProvider(DEFAULT_VISION)
        for info in [{'capabilities': ['completion']}, {'capabilities': ['vision'], 'remote_host': 'cloud.test'}]:
            with patch.object(provider, 'request', return_value=info), self.assertRaises(ValueError): provider.test()

    def test_points_are_strict_bounded_and_do_not_claim_confidence(self):
        provider = VisionProvider(DEFAULT_VISION)
        for point in [{'found': True, 'x': 1000, 'y': 30}, {'found': True, 'x': True, 'y': 2}, {'found': True, 'x': 0.5, 'y': 3}, {'found': 'yes', 'x': 4, 'y': 3}, {'found': True, 'x': 4, 'y': 3, 'confidence': 1}, ['point']]:
            with patch.object(provider, 'test'), patch.object(provider, 'request', return_value={'message': {'content': json.dumps(point)}}), self.assertRaises(ValueError):
                provider.point(IMAGE, 'Find target')
        with patch.object(provider, 'test'), patch.object(provider, 'request', return_value={'message': {'content': '{"found":true,"x":400,"y":500}'}, 'prompt_eval_count': 123, 'eval_count': 12}) as request:
            point = provider.point(IMAGE, 'Find target')
        payload = request.call_args.args[1]
        self.assertFalse(payload['stream']); self.assertFalse(payload['think'])
        self.assertEqual(payload['messages'][1]['images'], [IMAGE])
        self.assertEqual(point['usage'], {'prompt_tokens': 123, 'completion_tokens': 12})
        self.assertNotIn('confidence', point)

    def test_malformed_and_oversize_screenshot_rejected(self):
        for data in [b'junk', b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 9000, 800) + b'\0' * 9]:
            with self.assertRaises(ValueError): png_size(data)


class VisualActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.g = OpenRagnarGateway({'vision': {**DEFAULT_VISION, 'enabled': True}}, self.temp.name)
        self.viewport = {'url': 'https://example.com', 'width': 1000, 'height': 800, 'scrollX': 0, 'scrollY': 0, 'scale': 1, 'offsetX': 0, 'offsetY': 0, 'layout': 123}
        self.screen = {'result': {'content': [{'type': 'image', 'mimeType': 'image/png', 'data': IMAGE}]}}
        self.point = {'found': True, 'x': 400, 'y': 500, 'imageWidth': 1000, 'imageHeight': 800, 'usage': {'prompt_tokens': 123, 'completion_tokens': 12}}
        self.args = {'page': 10, 'instruction': 'Click the green triangle', 'action': 'click', 'successText': 'Vision test complete'}
    def tearDown(self):
        self.g.artifacts.cleanup(); self.g.moves_pool.shutdown(); self.temp.cleanup()

    def test_point_mode_never_clicks_and_uses_css_mapping(self):
        with patch.object(self.g, 'run_browser', side_effect=[self.viewport, {'stale': False, 'clicked': False}]) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', return_value=self.point):
            result = visual_act(self.g, {**self.args, 'action': 'point'}, 1)
        self.assertEqual((result['x'], result['y']), (400, 400))
        self.assertFalse(result['clicked']); self.assertFalse(result['verified'])
        self.assertFalse(result['screenshotReturnedToClient'])
        self.assertNotIn('p.clickAt', run.call_args_list[-1].args[0])

    def test_single_click_requires_fresh_page_and_text_verification(self):
        with patch.object(self.g, 'run_browser', side_effect=[self.viewport, {'stale': False, 'clicked': True}, {'matched': True}]) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', return_value=self.point):
            result = visual_act(self.g, self.args, 1)
        self.assertTrue(result['clicked']); self.assertTrue(result['verified'])
        script = run.call_args_list[1].args[0]
        self.assertLess(script.index('Object.keys(expected).every'), script.index('p.clickAt'))
        self.assertEqual(script.count('p.clickAt'), 1)

    def test_changed_page_not_found_and_cancellation_do_not_click(self):
        for point, cancelled in [(self.point, False), ({**self.point, 'found': False}, False), (self.point, True)]:
            if cancelled: self.g.cancelled.add(1)
            with patch.object(self.g, 'run_browser', side_effect=[self.viewport, {'stale': True}]) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', return_value=point):
                result = visual_act(self.g, self.args, 1)
            self.assertFalse(result['clicked']); self.assertFalse(result['verified'])
            self.assertEqual(run.call_count, 2 if point['found'] and not cancelled else 1)
            self.assertIn(result['status'], ('stale', 'not_found', 'cancelled'))

    def test_image_geometry_mismatch_stops_before_click(self):
        with patch.object(self.g, 'run_browser', return_value=self.viewport) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', return_value={**self.point, 'imageWidth': 800}), self.assertRaises(ValueError):
            visual_act(self.g, self.args, 1)
        self.assertEqual(run.call_count, 1)

    def test_model_failure_is_not_retried(self):
        with patch.object(self.g, 'run_browser', return_value=self.viewport) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', side_effect=ValueError('Model unavailable')) as model, self.assertRaises(ValueError):
            visual_act(self.g, self.args, 1)
        self.assertEqual(model.call_count, 1); self.assertEqual(run.call_count, 1)
        self.assertFalse(self.g.nav_lock.locked())

    def test_retina_capture_does_not_double_model_image_dimensions(self):
        with patch.object(self.g, 'run_browser', side_effect=[{**self.viewport, 'dpr': 2}, {'stale': False, 'clicked': False}]), patch.object(self.g, 'upstream_call', return_value=self.screen) as screen, patch('vision.VisionProvider.point', return_value=self.point):
            visual_act(self.g, {**self.args, 'action': 'point'}, 1)
        self.assertEqual(screen.call_args.args[0]['params']['arguments']['size'], {'width': 640, 'height': 480})

    def test_failed_verification_reports_that_click_already_happened(self):
        with patch.object(self.g, 'run_browser', side_effect=[self.viewport, {'stale': False, 'clicked': True}, ValueError('Verification transport failed')]) as run, patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', return_value=self.point):
            report = visual_act(self.g, self.args, 1)
        self.assertTrue(report['clicked']); self.assertFalse(report['verified'])
        self.assertEqual(report['status'], 'clicked_unverified')
        self.assertIn('do not repeat', report['reason'])
        self.assertEqual(run.call_count, 3)

    def test_vision_catalog_requires_enabled_setting(self):
        for enabled in [True, False]:
            self.g.settings['vision']['enabled'] = enabled
            response = self.g.transform({'method': 'tools/list'}, {'result': {'tools': []}})
            names = [t['name'] for t in response['result']['tools']]
            self.assertEqual('openragnar_visual_act' in names, enabled)
        with patch.object(self.g, 'run_browser') as run, self.assertRaises(ValueError): visual_act(self.g, self.args, 1)
        run.assert_not_called()


if __name__ == '__main__': unittest.main()
