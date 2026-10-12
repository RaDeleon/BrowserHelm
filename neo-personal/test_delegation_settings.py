"""Delegation opt-out, including clients with a cached catalog."""
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from browserhelm import BrowserHelmGateway


class DelegationSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.g = BrowserHelmGateway({'provider':'none','vision':{'enabled':True}}, self.temp.name)

    def tearDown(self):
        self.g.moves_pool.shutdown(wait=True)
        self.g.artifacts.cleanup()
        self.temp.cleanup()

    def catalog(self):
        response = {'result':{'tools':[{'name':'run'},{'name':'evaluate'},{'name':'screenshot'}]}}
        return {t['name'] for t in self.g.transform({'method':'tools/list'}, response)['result']['tools']}

    def test_legacy_default_preserves_delegation_and_off_preserves_direct_tools(self):
        self.assertTrue({'browserhelm_execute','browserhelm_navigate','browserhelm_visual_act'} <= self.catalog())
        self.g.settings['delegationEnabled'] = False
        tools = self.catalog()
        self.assertTrue({'run','evaluate','screenshot','browserhelm_task','browserhelm_status'} <= tools)
        self.assertFalse({'browserhelm_execute','browserhelm_navigate','browserhelm_visual_act'} & tools)

    def test_cached_delegated_calls_block_before_browser_models_or_keys(self):
        self.g.settings['delegationEnabled'] = False
        with patch('browserhelm.execute') as execute, patch.object(self.g,'navigate') as navigate, \
             patch('browserhelm.visual_act') as visual, patch.object(self.g,'upstream_call') as browser, \
             patch.object(self.g,'read_provider_key') as key:
            for name in ('browserhelm_execute','browserhelm_navigate','browserhelm_visual_act'):
                result = self.g._handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':{}}})
                self.assertTrue(result['result']['isError'])
                self.assertIn('disabled', result['result']['content'][0]['text'])
            for call in (execute,navigate,visual,browser,key): call.assert_not_called()

    def test_saved_switch_refreshes_existing_client_and_can_be_reenabled(self):
        path = pathlib.Path(self.temp.name)/'settings.json'
        self.g.settings_path = path
        for enabled in (True,False,True):
            path.write_text(json.dumps({'configVersion':3,'provider':'none','delegationEnabled':enabled,'vision':{'enabled':True}}))
            self.assertEqual('browserhelm_execute' in self.catalog(), enabled)
            self.assertEqual(self.g.delegation_enabled(), enabled)

    def test_bad_or_missing_saved_configuration_fails_closed(self):
        path = pathlib.Path(self.temp.name)/'settings.json'
        self.g.settings_path = path
        for contents in (None,'not json','[]','{"delegationEnabled":"false"}','{"delegationEnabled":null}'):
            if contents is None:
                path.unlink(missing_ok=True)
            else: path.write_text(contents)
            with patch('browserhelm.execute') as execute, patch.object(self.g,'upstream_call') as browser:
                result = self.g._handle({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'browserhelm_execute','arguments':{}}})
                self.assertTrue(result['result']['isError'])
                execute.assert_not_called(); browser.assert_not_called()

    def test_off_guidance_keeps_planning_with_host(self):
        self.g.settings['delegationEnabled'] = False
        result = self.g.transform({'method':'initialize'},{'result':{'instructions':'Neo instructions'}})['result']
        self.assertIn('delegation is disabled', result['instructions'])
        self.assertNotIn('Prefer browserhelm_execute', result['instructions'])

    def test_task_markers_opt_in_without_hiding_manual_tool(self):
        for enabled in (None, True, False):
            if enabled is None: self.g.settings.pop('agentTaskMarkers', None)
            else: self.g.settings['agentTaskMarkers'] = enabled
            instructions = self.g.transform({'method':'initialize'}, {'result':{'instructions':'Neo'}})['result']['instructions']
            self.assertEqual('For each new user prompt' in instructions, enabled is True)
            self.assertEqual('Task markers are optional' in instructions, enabled is not True)
            self.assertIn('browserhelm_task', self.catalog())

    def test_direct_browser_forwarding_still_available_while_off(self):
        self.g.settings['delegationEnabled'] = False
        request = {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'evaluate','arguments':{'page':1,'code':'return document.title;'}}}
        with patch.object(self.g,'upstream_call',return_value={'result':{'content':[{'type':'text','text':'Title'}]}}) as upstream, patch.object(self.g,'provider') as provider:
            result = self.g._handle(request)
        self.assertFalse(result['result'].get('isError',False))
        upstream.assert_called_once_with(request); provider.assert_not_called()


if __name__ == '__main__': unittest.main()
