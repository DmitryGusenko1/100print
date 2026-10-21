import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from app.organization.codex import ProductionCodexProvider
from app.organization.contracts import CHALLENGE
from app.providers import business_brain


class ProductionCodexTests(unittest.TestCase):
    def request(self):
        return {'operation':'challenge','output_schema':CHALLENGE,'input':{'question':'price'}}

    def test_identity_paths_and_timeout(self):
        with patch('os.getuid',return_value=0):
            with self.assertRaises(PermissionError): ProductionCodexProvider()
        for path in ('/tmp','/opt/ceo-orchestrator/jobs','/opt/ceo-orchestrator/.codex'):
            with self.assertRaises(ValueError): ProductionCodexProvider(path)
        for timeout in (0,-1,301,float('nan')):
            with self.assertRaises(ValueError): ProductionCodexProvider(timeout=timeout)
        with patch.dict(os.environ,{'CEO_BRAIN_MODE':'production'}):
            self.assertIsInstance(business_brain(),ProductionCodexProvider)
        with patch.dict(os.environ,{'CEO_BRAIN_MODE':'deterministic'}):
            with self.assertRaisesRegex(ValueError, 'requires production'):
                business_brain()

    def fake(self, value, code=0, timeout=False):
        def popen(command, **kwargs):
            self.command=command; self.environment=kwargs['env']
            class Process:
                pid=12345
                returncode=code
                calls=0
                def communicate(inner, *args, **kw):
                    inner.calls+=1
                    if timeout and inner.calls==1: raise subprocess.TimeoutExpired(command,1)
                    Path(command[command.index('--output-last-message')+1]).write_text(value)
            return Process()
        return popen

    def test_strict_json_and_no_credentials_inherited(self):
        valid={'challenges':['Margin unknown'],'evidence_gaps':['COGS'],
               'blocking':True,'alternative_hypotheses':['Value rather than price constrains demand']}
        with patch('subprocess.Popen',side_effect=self.fake(json.dumps(valid))):
            self.assertEqual(ProductionCodexProvider().respond(self.request()),valid)
        self.assertEqual(set(self.environment),{'PATH','HOME','CODEX_HOME','LANG'})
        for flag in ('--ephemeral','--ignore-user-config','--ignore-rules','--output-schema'):
            self.assertIn(flag,self.command)
        self.assertIn('features.shell_tool=false',self.command)
        self.assertIn('features.plugins=false',self.command)
        for invalid in ('{}','not JSON',json.dumps({**valid,'hidden_reasoning':'x'}),
                        json.dumps({k:v for k,v in valid.items() if k!='alternative_hypotheses'})):
            with self.subTest(value=invalid),patch('subprocess.Popen',side_effect=self.fake(invalid)):
                with self.assertRaises((ValueError, __import__('jsonschema').ValidationError)):
                    ProductionCodexProvider().respond(self.request())

    def test_failure_timeout_never_falls_back(self):
        with patch('subprocess.Popen',side_effect=self.fake('{}',code=1)):
            with self.assertRaises(RuntimeError): ProductionCodexProvider().respond(self.request())
        with patch('subprocess.Popen',side_effect=self.fake('{}',timeout=True)),patch('os.killpg') as kill:
            with self.assertRaisesRegex(RuntimeError,'timeout'): ProductionCodexProvider().respond(self.request())
            kill.assert_called_once()

    def test_model_metadata_prevents_mixed_checkpoint_replay(self):
        from app.organization.engine import Organization
        from app.organization.brain import DeterministicBrainProvider
        from app.organization.store import MemoryStore
        from tests.test_organization import task
        store=MemoryStore()
        first=ProductionCodexProvider(model='model-one')
        with patch.object(first,'respond',side_effect=DeterministicBrainProvider().respond):
            Organization(first,store).execute(task('L1',['seo']))
        second=ProductionCodexProvider(model='model-two')
        with patch.object(second,'respond') as respond:
            with self.assertRaisesRegex(ValueError,'changed'):
                Organization(second,store).execute(task('L1',['seo']))
            respond.assert_not_called()
