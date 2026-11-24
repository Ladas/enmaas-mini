#!/usr/bin/env python3
"""Named, isolated Terraform working directories. Never stores AWS credentials."""
import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

MODULE = Path(__file__).resolve().parents[2] / 'infra/terraform/aws'


def identifier(value):
    if not re.fullmatch(r'em-[a-z][a-z0-9]{1,7}-[a-f0-9]{12}', value):
        raise ValueError('Invalid deployment ID')
    return value


def private_directory(path, create=False):
    if path.is_symlink():
        raise ValueError('State directory must not be a symlink')
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError('State directory must be owned by you and mode 0700')
    return path


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    path.chmod(0o600)


def initialize(root, config, profile):
    required = {'account_id','group','ami_id','ami_owner_id','availability_zones',
                'ssh_cidrs','https_cidrs','ssh_public_key'}
    allowed = required | {'region','topology','vpc_cidr'}
    if not required <= config.keys() or config.keys() - allowed:
        raise ValueError('Use only module inputs; no credentials or deployment ID')
    if not re.fullmatch(r'[a-z][a-z0-9]{1,7}', config['group']):
        raise ValueError('Group must be 2–8 lowercase letters/digits')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', profile):
        raise ValueError('Supply an AWS profile name, not credentials')
    deployment = 'em-' + config['group'] + '-' + secrets.token_hex(6)
    folder = private_directory(root / deployment, create=True)
    for file in MODULE.glob('*.tf'):
        shutil.copyfile(file, folder / file.name)
    lock = MODULE / '.terraform.lock.hcl'
    if lock.exists():
        shutil.copyfile(lock, folder / lock.name)
    write_json(folder / 'terraform.tfvars.json', dict(config, deployment_id=deployment))
    write_json(folder / 'selection.json', {'profile':profile, 'deployment':deployment})
    return deployment


def environment(profile):
    env = dict(os.environ)
    # An inherited key must never silently override the selected role profile.
    for key in list(env):
        if key.startswith(('AWS_', 'TF_VAR_', 'TF_CLI_ARGS')):
            del env[key]
    env.update(AWS_PROFILE=profile, AWS_SDK_LOAD_CONFIG='1', TF_IN_AUTOMATION='1')
    return env


def terraform(folder, binary, args, capture=False):
    profile = json.loads((folder/'selection.json').read_text())['profile']
    return subprocess.run([binary, '-chdir='+str(folder), *args], env=environment(profile),
                          text=True, check=True, capture_output=capture)


def operate(folder, binary, action, confirmation=None):
    deployment = identifier(folder.name)
    plan = folder / 'reviewed.tfplan'
    receipt = folder / 'reviewed-plan.json'
    if action in ('plan','destroy-plan'):
        terraform(folder,binary,['init','-input=false'])
        args=['plan','-input=false','-out='+str(plan)]
        if action == 'destroy-plan': args.append('-destroy')
        terraform(folder,binary,args)
        if receipt.exists(): receipt.unlink()
        write_json(receipt, {'action':action,'sha256':hashlib.sha256(plan.read_bytes()).hexdigest()})
    elif action == 'apply':
        metadata=json.loads(receipt.read_text())
        verb='destroy' if metadata['action']=='destroy-plan' else 'apply'
        if confirmation != verb+' '+deployment:
            raise ValueError('Required confirmation: '+verb+' '+deployment)
        if hashlib.sha256(plan.read_bytes()).hexdigest()!=metadata['sha256']:
            raise ValueError('Plan changed; regenerate and review it')
        terraform(folder,binary,['apply','-input=false',str(plan)])
        plan.unlink(); receipt.unlink()
    elif action == 'info':
        result=terraform(folder,binary,['output','-json','deployment'],capture=True)
        inventory=json.loads(result.stdout)
        if inventory.get('deployment_id')!=deployment:
            raise ValueError('Inventory belongs to another deployment')
        print(json.dumps(inventory,indent=2))
    elif action == 'show':
        terraform(folder,binary,['show',str(plan)])


def service_config(inventory, options):
    """Convert infrastructure output to the existing three-host installer contract."""
    deployment=identifier(inventory['deployment_id'])
    if inventory.get('topology')!='full' or set(inventory['hosts'])!={'gateway','keycloak','observability'}:
        raise ValueError('Full service handoff requires exactly three hosts')
    if not re.fullmatch(r'[a-f0-9]{40}',options['revision']):
        raise ValueError('Pin a reviewed 40-character service commit')
    if not re.fullmatch(r'https://github[.]com/[A-Za-z0-9-]+/enmaas-mini[.]git',options['source_repository']):
        raise ValueError('Use a credential-free enmaas-mini GitHub URL')
    for field in ('ssh_key','known_hosts','tls_directory'):
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+',options[field]) or '..' in Path(options[field]).parts:
            raise ValueError('Use absolute simple paths for '+field)
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+',options['issuer_name']):
        raise ValueError('Use a canonical issuer DNS name; configure workstation resolution separately')
    if ipaddress.IPv4Network(options['workstation_cidr']).prefixlen!=32:
        raise ValueError('Use a workstation /32')
    hosts={}
    for role,host in inventory['hosts'].items():
        public=str(ipaddress.IPv4Address(host['public_ip']))
        private=ipaddress.IPv4Address(host['private_ip'])
        if not any(private in ipaddress.IPv4Network(cidr) for cidr in
                   ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
            raise ValueError('An RFC1918 private peer address is required')
        hosts[role]={'ssh':'ec2-user@'+public,'private_ip':str(private)}
    if len({host['ssh'] for host in hosts.values()})!=3 or len({host['private_ip'] for host in hosts.values()})!=3:
        raise ValueError('Use three distinct public and private host addresses')
    return dict(options,version=1,deployment=deployment,repository='/opt/enmaas-mini/'+deployment,
                external_database=False,hosts=hosts,population_count=10000)


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.home()/'.local/state/enmaas-terraform')
    p.add_argument('--terraform',default='terraform')
    commands=p.add_subparsers(dest='command',required=True)
    init=commands.add_parser('init'); init.add_argument('--config',type=Path,required=True)
    init.add_argument('--profile',required=True)
    commands.add_parser('list')
    export=commands.add_parser('services-config')
    export.add_argument('deployment',type=identifier)
    export.add_argument('--options',type=Path,required=True)
    for name in ('plan','destroy-plan','apply','info','show'):
        cmd=commands.add_parser(name); cmd.add_argument('deployment',type=identifier)
        if name=='apply': cmd.add_argument('--confirm',required=True)
    args=p.parse_args(); root=private_directory(args.root.absolute(),create=True)
    if args.command=='init':
        print(initialize(root,json.loads(args.config.read_text()),args.profile))
    elif args.command=='list':
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and not entry.is_symlink() and re.fullmatch(r'em-[a-z][a-z0-9]{1,7}-[a-f0-9]{12}',entry.name):
                print(entry.name)
    elif args.command=='services-config':
        folder=private_directory(root/args.deployment)
        inventory=json.loads(terraform(folder,args.terraform,['output','-json','deployment'],capture=True).stdout)
        if inventory.get('deployment_id')!=args.deployment:raise ValueError('Wrong deployment inventory')
        options=json.loads(args.options.read_text())
        required={'revision','source_repository','ssh_key','known_hosts','tls_directory','issuer_name','workstation_cidr'}
        if set(options)!=required:raise ValueError('Use only documented installer options')
        target=folder/'services.json'
        write_json(target,service_config(inventory,options))
        print(target)
    else:
        folder=private_directory(root/args.deployment)
        with (folder/'operation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            operate(folder,args.terraform,args.command,getattr(args,'confirm',None))


if __name__=='__main__':
    try: main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('Stopped: '+str(error),file=sys.stderr); sys.exit(1)
