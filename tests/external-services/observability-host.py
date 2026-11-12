#!/usr/bin/env python3
"""Prepare rootless observation-host inputs; credentials stay in private files."""
import argparse
import importlib.util
import ipaddress
from pathlib import Path
import stat
import tempfile
import yaml

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('local_lab',HERE/'local.py')
lab=importlib.util.module_from_spec(spec);spec.loader.exec_module(lab)


def privacy_transform():
    resource=['keep_keys(attributes, ["service.name", "service.version", "deployment.environment.name"])']
    scope=['set(name, "enmaas")','set(version, "")','keep_keys(attributes, [])']
    attributes='keep_keys(attributes, ["http.request.method", "http.response.status_code", "error.type", "gen_ai.provider.name", "gen_ai.request.model"])'
    transform={'error_mode':'propagate',
        'log_statements':[{'context':'resource','statements':resource},{'context':'scope','statements':scope},
            {'context':'log','statements':[attributes,'set(body, "gateway event")','set(severity_text, "")']}],
        'trace_statements':[{'context':'resource','statements':resource},{'context':'scope','statements':scope},
            {'context':'span','statements':[attributes,'set(name, "request")','set(status.message, "")','set(trace_state, "")','set(links, nil)']},
            {'context':'spanevent','statements':['set(name, "event")','keep_keys(attributes, [])']}],
        'metric_statements':[{'context':'resource','statements':resource},{'context':'scope','statements':scope},
            {'context':'metric','statements':['set(description, "")','set(unit, "")']},
            {'context':'datapoint','statements':['keep_keys(attributes, ["http.request.method", "http.response.status_code", "gen_ai.request.model", "state", "cpu", "device", "direction", "type", "cluster", "route", "listener", "endpoint", "method", "status_class", "filter", "phase", "quantile", "le", "result", "reason"])','set(exemplars, nil) where metric.type != METRIC_DATA_TYPE_SUMMARY']}]}
    return transform


def configure(root,issuer,observability,client_secret):
    issuer,observability=(str(ipaddress.IPv4Address(value)) for value in (issuer,observability))
    if not 16<=len(client_secret)<=4096 or any(not 33<=ord(c)<=126 or c in '\\"' for c in client_secret):
        raise ValueError('invalid confidential-client secret; use visible ASCII without quotes/backslashes')
    if any(root.iterdir()):raise FileExistsError('use a new empty output directory')
    root.chmod(0o700)
    names=('oauth.cfg','perses.yaml','prometheus.yaml','loki.yaml','tempo.yaml','collector.yaml',
           *lab.PERSES_ASSETS)
    with tempfile.TemporaryDirectory() as temporary:
        source=Path(temporary);lab.configure(source,certificates=False)
        for name in names:lab.write(root,name,(source/name).read_text())
    auth=(root/'oauth.cfg').read_text()
    lines=[]
    for line in auth.splitlines():
        if line.startswith('client_secret ='):line='client_secret = "'+client_secret+'"'
        elif line.startswith('email_domains ='):line='email_domains = ["*"]' # explicit group gate remains mandatory
        lines.append(line)
    auth='\n'.join(lines)+'\n'
    auth=auth.replace('https://localhost:18443',f'https://{issuer}:8443')
    auth=auth.replace('https://localhost:19443',f'https://{observability}:8443')
    auth=auth.replace('0.0.0.0:19443','0.0.0.0:8443').replace('/lab/ca.pem','/lab/issuer-ca.pem')
    lab.write(root,'oauth.cfg',auth)
    collector=yaml.safe_load((root/'collector.yaml').read_text())
    collector['receivers']['otlp']['protocols']['http']['tls']['client_ca_file']='/lab/telemetry-ca.pem'
    # Raw log text, URLs, request headers and user identifiers are never required
    # for this test-host dashboard. Keep only reviewed bounded label names.
    transform=privacy_transform()
    collector['processors']['transform']=transform
    collector['service']['pipelines']['metrics']['processors']=['memory_limiter','transform','batch']
    for name in ('otlphttp/loki','otlphttp/tempo'):
        collector['exporters'][name]['sending_queue']={'enabled':True,'queue_size':256,'num_consumers':2}
        collector['exporters'][name]['retry_on_failure']={'enabled':True,'max_elapsed_time':'30s'}
    lab.write(root,'collector.yaml',yaml.safe_dump(collector,sort_keys=False))
    units=root/'quadlets';units.mkdir(mode=0o700)
    lab.write(units,'lab-observability.pod','[Pod]\nPodName=lab-observability\nPublishPort=8443:8443\nPublishPort=24443:24443\n[Install]\nWantedBy=default.target\n')
    components={
        'auth':('oauth.cfg','--config=/lab/oauth.cfg','256M',None),
        'perses':('perses.yaml','--config=/lab/perses.yaml','512M','/perses'),
        'prometheus':('prometheus.yaml','--config.file=/lab/prometheus.yaml --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=48h --storage.tsdb.retention.size=512MB','1G','/prometheus'),
        'loki':('loki.yaml','-config.file=/lab/loki.yaml','1G','/loki'),
        'tempo':('tempo.yaml','-config.file=/lab/tempo.yaml','1G','/var/tempo'),
        'collector':('collector.yaml','--config=/lab/collector.yaml','512M',None)}
    for name,(config,command,memory,volume) in components.items():
        body=f'[Container]\nImage={lab.IMAGES[name]}\nPod=lab-observability.pod\nContainerName=lab-obs-{name}\nNoNewPrivileges=true\nDropCapability=all\nPidsLimit=256\n'
        body+=f'Secret=lab-obs-{config.replace(".","-")},target=/lab/{config}\nExec={command}\n'
        if name in ('auth','collector'):
            body+='Secret=lab-obs-server-cert,target=/lab/server.pem\nSecret=lab-obs-server-key,target=/lab/server.key\n'
            ca='issuer' if name=='auth' else 'telemetry'
            body+=f'Secret=lab-obs-{ca}-ca,target=/lab/{ca}-ca.pem\n'
        if name=='perses':
            for asset in lab.PERSES_ASSETS:
                body+=f'Secret=lab-obs-{asset.replace(".","-")},target=/etc/perses/lab/{asset}\n'
        if volume:
            lab.write(units,f'lab-obs-{name}.volume',f'[Volume]\nVolumeName=enmaas-lab-obs-{name}\n')
            body+=f'Volume=lab-obs-{name}.volume:{volume}:U\n'
        body+=f'[Service]\nMemoryMax={memory}\nRestart=on-failure\nTimeoutStartSec=300\n[Install]\nWantedBy=default.target\n'
        lab.write(units,f'lab-obs-{name}.container',body)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issuer',required=True)
    parser.add_argument('--observability',required=True)
    parser.add_argument('--client-secret-file',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    info=args.client_secret_file.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077:
        parser.error('client secret must be a private regular file')
    with args.client_secret_file.open() as source:secret=source.read(4097).strip()
    args.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    configure(args.output,args.issuer,args.observability,secret)
    print('Private observability inputs prepared; no services started.')

if __name__=='__main__':main()
