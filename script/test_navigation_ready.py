"""Exercise the page-side readiness promise, including delayed content and cleanup."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest


NODE = shutil.which('node')
SOURCE = Path(__file__).resolve().parents[1] / 'neo-personal/openragnar.py'


@unittest.skipUnless(NODE, 'Node is needed to execute the page-side JavaScript tests')
class NavigationReadyTests(unittest.TestCase):
    def run_ready(self, mode):
        tree = ast.parse(SOURCE.read_text())
        ready = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'NAV_READY_JS' for t in n.targets))
        harness = '''
const mode = MODE;
const timers = new Map(); let disconnected = 0, observerCallback, links = [];
const document = {body: {innerText: ''}, documentElement: {}, querySelectorAll: () => links};
const setTimeout = (fn, delay) => { if(delay!==8000) throw Error('unexpected deadline'); timers.set(1,fn); return 1; };
const clearTimeout = id => timers.delete(id);
class MutationObserver {
  constructor(callback) { observerCallback = callback; }
  observe(node, options) { if(!options.subtree || !options.characterData || !options.childList) throw Error('missing observation'); }
  disconnect() { disconnected++; }
}
if(mode==='present') document.body.innerText = 'The TARGET PHRASE exists.';
if(mode==='link') links = [{getClientRects: () => [1], hasAttribute: () => false}];
if(mode==='timeout') links = [{getClientRects: () => [], hasAttribute: () => false}];
const result = (READY)({needle: 'target phrase'});
if(mode==='delayed') { document.body.innerText = 'target phrase'; observerCallback(); }
if(mode==='timeout') timers.get(1)();
result.then(value => console.log(JSON.stringify({value, pendingTimers:timers.size, disconnected}))).catch(error=>{console.error(error);process.exitCode=1;});
'''.replace('MODE', json.dumps(mode)).replace('READY', ready)
        result = subprocess.run([NODE, '-e', harness], text=True, capture_output=True, check=True, timeout=5)
        return json.loads(result.stdout)

    def test_existing_answer_needs_no_link_or_timer(self):
        self.assertEqual(self.run_ready('present'), {'value': True, 'pendingTimers': 0, 'disconnected': 0})

    def test_visible_link_allows_observation(self):
        self.assertTrue(self.run_ready('link')['value'])

    def test_delayed_answer_resolves_and_releases_observer_and_timer(self):
        self.assertEqual(self.run_ready('delayed'), {'value': True, 'pendingTimers': 0, 'disconnected': 1})

    def test_hidden_link_does_not_bypass_bounded_timeout(self):
        self.assertEqual(self.run_ready('timeout'), {'value': False, 'pendingTimers': 0, 'disconnected': 1})


if __name__ == '__main__':
    unittest.main()
