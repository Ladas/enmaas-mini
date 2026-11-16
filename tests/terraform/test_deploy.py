import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deploy',Path(__file__).with_name('deploy.py'))
deploy=importlib.util.module_from_spec(spec);spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=dict(account_id='123456789012',group='test',ami_id='ami-12345678',
                         ami_owner_id='123456789012',availability_zones=['eu-central-1a'],
                         ssh_cidrs=['192.0.2.1/32'],https_cidrs=['192.0.2.1/32'],
                         ssh_public_key='ssh-ed25519 AAAA fixture')
        self.name=deploy.initialize(self.root,self.config,'test-role')
        self.folder=self.root/self.name

    def test_isolated_deployments(self):
        other=deploy.initialize(self.root,self.config,'test-role')
        self.assertNotEqual(self.name,other)
        self.assertEqual(self.folder.stat().st_mode&0o777,0o700)
        self.assertEqual((self.folder/'selection.json').stat().st_mode&0o777,0o600)
        self.assertTrue((self.folder/'main.tf').exists())

    def test_no_credentials_in_configuration(self):
        for key in ('access_key','secret_key','deployment_id'):
            with self.assertRaises(ValueError):
                deploy.initialize(self.root,dict(self.config,**{key:'secret'}),'role')

    def test_clear_ambient_credentials_and_cli_injection(self):
        with patch.dict(os.environ,{'AWS_ACCESS_KEY_ID':'secret','AWS_ENDPOINT_URL':'http://evil',
                                   'TF_CLI_ARGS_apply':'-auto-approve','TF_VAR_group':'other'}):
            env=deploy.environment('scoped')
        self.assertNotIn('AWS_ACCESS_KEY_ID',env)
        self.assertNotIn('AWS_ENDPOINT_URL',env)
        self.assertNotIn('TF_CLI_ARGS_apply',env)
        self.assertNotIn('TF_VAR_group',env)
        self.assertEqual(env['AWS_PROFILE'],'scoped')

    def test_reject_traversal_and_shared_state(self):
        for value in ('../state','em-test-xyz','/tmp/state'):
            with self.assertRaises(ValueError): deploy.identifier(value)
        self.folder.chmod(0o755)
        with self.assertRaises(ValueError):deploy.private_directory(self.folder)

    def test_reject_symlink(self):
        link=self.root/'link';link.symlink_to(self.folder)
        with self.assertRaises(ValueError):deploy.private_directory(link)

    def test_plan_apply_and_destroy_with_mock_engine(self):
        calls=[]
        def fake(folder,binary,args,**kwargs):
            calls.append(args)
            if args[0]=='plan':(folder/'reviewed.tfplan').write_bytes(b'mocked plan')
        with patch.object(deploy,'terraform',side_effect=fake):
            for action,verb in [('plan','apply'),('destroy-plan','destroy')]:
                deploy.operate(self.folder,'terraform',action)
                with self.assertRaises(ValueError):deploy.operate(self.folder,'terraform','apply','wrong')
                deploy.operate(self.folder,'terraform','apply',verb+' '+self.name)
                self.assertFalse((self.folder/'reviewed.tfplan').exists())
        self.assertEqual(sum(c[0]=='apply' for c in calls),2)
        self.assertTrue(any('-destroy' in c for c in calls))

    def test_modified_plan_rejected(self):
        def fake(folder,binary,args,**kwargs):
            if args[0]=='plan':(folder/'reviewed.tfplan').write_bytes(b'original')
        with patch.object(deploy,'terraform',side_effect=fake):
            deploy.operate(self.folder,'terraform','plan')
            (self.folder/'reviewed.tfplan').write_bytes(b'changed')
            with self.assertRaises(ValueError):deploy.operate(self.folder,'terraform','apply','apply '+self.name)

    def test_failed_apply_preserves_recovery_plan(self):
        import subprocess
        def fake(folder,binary,args,**kwargs):
            if args[0]=='plan':(folder/'reviewed.tfplan').write_bytes(b'original')
            if args[0]=='apply':raise subprocess.CalledProcessError(1,args)
        with patch.object(deploy,'terraform',side_effect=fake):
            deploy.operate(self.folder,'terraform','plan')
            with self.assertRaises(subprocess.CalledProcessError):
                deploy.operate(self.folder,'terraform','apply','apply '+self.name)
        self.assertTrue((self.folder/'reviewed.tfplan').exists())

    def test_service_handoff_and_identity(self):
        inventory={'deployment_id':self.name,'topology':'full','hosts':{
            role:{'public_ip':f'192.0.2.{index+1}','private_ip':f'10.80.{index}.10'}
            for index,role in enumerate(('gateway','keycloak','observability'))}}
        options=dict(revision='a'*40,source_repository='https://github.com/Ladas/enmaas-mini.git',
                     ssh_key='/private/test/key',known_hosts='/private/test/known_hosts',
                     tls_directory='/private/test/tls',issuer_name='identity.example.test',
                     workstation_cidr='192.0.2.50/32')
        result=deploy.service_config(inventory,options)
        self.assertEqual(result['hosts']['gateway']['ssh'],'ec2-user@192.0.2.1')
        self.assertEqual(result['repository'],'/opt/enmaas-mini/'+self.name)
        self.assertFalse(result['external_database'])
        self.assertEqual(result['population_count'],10000)
        for key,value in [('revision','main'),('ssh_key','/tmp/../key'),
                          ('source_repository','https://token@github.com/Ladas/enmaas-mini.git'),
                          ('workstation_cidr','0.0.0.0/0'),('issuer_name','https://bad')]:
            with self.assertRaises(ValueError):deploy.service_config(inventory,dict(options,**{key:value}))
        original=inventory['hosts']['gateway']['private_ip']
        for address in ('127.0.0.1','192.0.2.10',inventory['hosts']['keycloak']['private_ip']):
            inventory['hosts']['gateway']['private_ip']=address
            with self.assertRaises(ValueError):deploy.service_config(inventory,options)
        inventory['hosts']['gateway']['private_ip']=original
        inventory['topology']='single'
        with self.assertRaises(ValueError):deploy.service_config(inventory,options)

    def test_cli_lifecycle_with_mock_terraform_process(self):
        import subprocess
        import sys
        binary=self.root/'terraform-mock'
        binary.write_text('''#!/usr/bin/env python3
import json,sys,pathlib
p=pathlib.Path(sys.argv[1].split('=',1)[1]); args=sys.argv[2:]
if args[0]=='plan': (p/'reviewed.tfplan').write_bytes(b'mocked AWS plan')
elif args[0]=='output': print(json.dumps({'deployment_id':p.name,'hosts':{}}))
elif args[0] not in ('init','show','apply'): raise SystemExit(2)
''')
        binary.chmod(0o700)
        cmd=[sys.executable,str(Path(deploy.__file__)), '--root',str(self.root),
             '--terraform',str(binary)]
        def run(*args):return subprocess.run(cmd+list(args),capture_output=True,text=True,check=True)
        self.assertIn(self.name,run('list').stdout)
        run('plan',self.name);run('show',self.name)
        run('apply',self.name,'--confirm','apply '+self.name)
        self.assertEqual(json.loads(run('info',self.name).stdout)['deployment_id'],self.name)
        run('destroy-plan',self.name)
        run('apply',self.name,'--confirm','destroy '+self.name)

if __name__=='__main__':unittest.main()
