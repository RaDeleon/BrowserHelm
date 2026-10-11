"""Grounding and action boundary tests; no actual model, network or browser."""
import base64
import json
import struct
import tempfile
import unittest
import zlib
from unittest.mock import patch
from openragnar import OpenRagnarGateway
from experience import ExperienceMemory
from vision import VisionProvider, local_endpoint, png_size, target_pixels, visual_act, DEFAULT_VISION

def image_png(width=1000, height=800, color=(10,20,30), changed=None, filtered=False):
    def chunk(kind, body):
        return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
    rows, previous = [], bytes(width*3)
    for y in range(height):
        row = bytearray(bytes(color)*width)
        if changed and changed[1]==y: row[changed[0]*3:changed[0]*3+3] = bytes((250,240,230))
        rows.append((b'\2'+bytes((a-b)&255 for a,b in zip(row,previous))) if filtered else b'\0'+row)
        previous = row
    data = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>II',width,height)+bytes((8,2,0,0,0)))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
    return base64.b64encode(data).decode()


IMAGE = image_png()


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

    def test_target_pixels_ignore_unrelated_changes_but_detect_changed_control(self):
        original = image_png(256,128)
        unrelated = image_png(256,128,changed=(0,0))
        target = image_png(256,128,changed=(128,64))
        filtered = image_png(256,128,filtered=True)
        fingerprint = target_pixels(original,500,500)
        self.assertEqual(target_pixels(unrelated,500,500), fingerprint)
        self.assertEqual(target_pixels(filtered,500,500), fingerprint)
        self.assertNotEqual(target_pixels(target,500,500), fingerprint)
        data = bytearray(base64.b64decode(original)); data[-5] ^= 1
        with self.assertRaises(ValueError): target_pixels(base64.b64encode(data).decode(),500,500)


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

    def test_canvas_pixel_change_stops_click_even_when_dom_is_unchanged(self):
        changed = {'result': {'content': [{'type': 'image', 'mimeType': 'image/png', 'data': image_png(color=(50,60,70))}]}}
        with patch.object(self.g, 'run_browser', return_value=self.viewport.copy()) as run, patch.object(self.g, 'upstream_call', side_effect=[self.screen, changed]), patch('vision.VisionProvider.point', return_value=self.point):
            report = visual_act(self.g, self.args, 1)
        self.assertEqual(report['status'], 'stale'); self.assertFalse(report['clicked'])
        self.assertEqual(run.call_count, 1)

    def test_existing_success_text_does_not_click_or_get_learning_credit(self):
        with patch.object(self.g, 'run_browser', return_value={**self.viewport, 'successPresent': True}), patch.object(self.g, 'upstream_call') as screen, patch('vision.VisionProvider.point') as model:
            report = visual_act(self.g, self.args, 1)
        self.assertEqual(report['status'], 'already_satisfied'); self.assertFalse(report['clicked'])
        screen.assert_not_called(); model.assert_not_called()

    def test_vision_catalog_requires_enabled_setting(self):
        for enabled in [True, False]:
            self.g.settings['vision']['enabled'] = enabled
            response = self.g.transform({'method': 'tools/list'}, {'result': {'tools': []}})
            names = [t['name'] for t in response['result']['tools']]
            self.assertEqual('openragnar_visual_act' in names, enabled)
        with patch.object(self.g, 'run_browser') as run, self.assertRaises(ValueError): visual_act(self.g, self.args, 1)
        run.assert_not_called()


class VisualLearningTests(unittest.TestCase):
    def setUp(self):
        VisualActionTests.setUp(self)
        config = self.g.artifacts.root/'ovcli.conf'
        config.write_text(json.dumps({'url': 'http://127.0.0.1:1933', 'user': 'vision-test'}))
        self.g.memory = ExperienceMemory({'enabled': True, 'validation': True}, config.parent/'experiences.sqlite', config)
        self.viewport['successPresent'] = False

    tearDown = VisualActionTests.tearDown

    def attempt(self, arguments=None, verified=True, image=None):
        with patch.object(self.g, 'run_browser', side_effect=[self.viewport.copy(), {'stale': False, 'clicked': True}, {'matched': verified}]), patch.object(self.g, 'upstream_call', return_value=image or self.screen), patch('vision.VisionProvider.point', return_value=self.point) as model:
            report = visual_act(self.g, arguments or self.args, 1)
        return report, model.call_count

    def test_two_verified_runs_then_reuse_survives_restart_and_upload_has_no_private_target(self):
        first, a = self.attempt(); second, b = self.attempt()
        memory = self.g.memory
        self.g.memory = ExperienceMemory({'enabled': True}, memory.path, memory.config_path)
        third, c = self.attempt()
        self.assertEqual([a,b,c], [1,1,0]); self.assertTrue(third['verified'])
        self.assertEqual(third['groundingSource'], 'verified_local_memory')
        self.assertEqual(third['usage']['total_tokens'], 0)
        self.assertEqual(third['memory']['providerCallsAvoided'], 1)
        self.assertEqual(self.g.memory.snapshot()['visual_reuse_verified'], 1)
        with memory.db() as db: records = [json.loads(row[0]) for row in db.execute('SELECT document FROM experiences')]
        self.assertTrue(records[0]['test'])
        for document in records:
            self.assertNotIn('x', document); self.assertNotIn('scene', document)
            self.assertNotIn(self.args['instruction'], json.dumps(document))
            self.assertNotIn(self.args['successText'], json.dumps(document))
            self.assertNotIn(self.viewport['url'], json.dumps(document))

    def test_failed_reuse_is_revoked_until_two_new_model_successes(self):
        self.attempt(); self.attempt()
        failed, a = self.attempt(verified=False)
        one, b = self.attempt(); two, c = self.attempt(); recovered, d = self.attempt()
        self.assertEqual([a,b,c,d], [0,1,1,0])
        self.assertTrue(failed['clicked']); self.assertFalse(failed['verified'])
        self.assertEqual(one['memory']['priorMatchingFailures'], 1)
        self.assertTrue(recovered['verified'])

    def test_reused_successes_do_not_replace_independent_evidence(self):
        self.attempt(); self.attempt()
        for _ in range(30):
            report, calls = self.attempt()
            self.assertEqual(calls, 0)
            self.assertEqual(report['memory']['verifiedModelRuns'], 2)
        self.attempt(verified=False)
        self.assertEqual(self.attempt()[1], 1)

    def test_scene_instruction_postcondition_model_and_account_are_isolated(self):
        self.attempt(); self.attempt()
        changed = {'result': {'content': [{'type': 'image', 'mimeType': 'image/png', 'data': image_png(color=(50,60,70))}]}}
        self.assertEqual(self.attempt(image=changed)[1], 1)
        self.assertEqual(self.attempt({**self.args, 'instruction': 'Different target'})[1], 1)
        self.assertEqual(self.attempt({**self.args, 'successText': 'Different outcome'})[1], 1)
        self.g.settings['vision']['model'] = 'other-local-model'
        self.assertEqual(self.attempt()[1], 1)
        self.g.settings['vision']['model'] = DEFAULT_VISION['model']
        self.g.memory.config_path.write_text(json.dumps({'url': 'http://127.0.0.1:1933', 'user': 'other-account'}))
        self.assertEqual(self.attempt()[1], 1)

    def test_old_or_corrupt_evidence_does_not_authorize_reuse(self):
        self.attempt(); self.attempt()
        with self.g.memory.db() as db: db.execute('UPDATE visual_history SET point=?', (json.dumps({**self.point, 'x': -1}),))
        self.assertEqual(self.attempt()[1], 1)
        with self.g.memory.db() as db: db.execute('UPDATE visual_history SET created=0')
        self.assertEqual(self.attempt()[1], 1)

    def test_disabled_or_unavailable_memory_does_not_prevent_model_execution(self):
        self.g.memory.initial_enabled = False
        report, calls = self.attempt()
        self.assertTrue(report['verified']); self.assertEqual(calls, 1)
        self.g.memory.initial_enabled = True
        with patch.object(self.g.memory, 'visual_evidence', side_effect=OSError('Unavailable')):
            report, calls = self.attempt()
        self.assertTrue(report['verified']); self.assertEqual(calls, 1)

    def test_point_only_and_unverified_clicks_cannot_promote_reuse(self):
        for _ in range(3): self.attempt(verified=False)
        report, calls = self.attempt()
        self.assertEqual(calls, 1)
        self.assertEqual(report['memory']['verifiedModelRuns'], 0)
        with self.g.memory.db() as db: before = db.execute('SELECT COUNT(*) FROM visual_history').fetchone()[0]
        with patch.object(self.g, 'run_browser', side_effect=[self.viewport.copy(), {'stale': False, 'clicked': False}]), patch.object(self.g, 'upstream_call', return_value=self.screen), patch('vision.VisionProvider.point', return_value=self.point):
            visual_act(self.g, {**self.args, 'action': 'point'}, 1)
        with self.g.memory.db() as db: after = db.execute('SELECT COUNT(*) FROM visual_history').fetchone()[0]
        self.assertEqual(before, after)


if __name__ == '__main__': unittest.main()
