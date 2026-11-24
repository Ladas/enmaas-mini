"""One canonical OIDC identity with an optional private address for server peers."""
import importlib.util
import ipaddress
from pathlib import Path

path=Path(__file__).resolve().parent/'certificates.py'
spec=importlib.util.spec_from_file_location('issuer_certificate_names',path)
certificates=importlib.util.module_from_spec(spec);spec.loader.exec_module(certificates)


def resolve(public_ip,name=None,private_ip=None):
    public_ip=str(ipaddress.IPv4Address(public_ip))
    if name is None and private_ip is None:return public_ip,None
    if not isinstance(name,str) or not name or private_ip is None:
        raise ValueError('supply both issuer DNS name and private IPv4 address')
    name=certificates.dns_name(name)
    address=ipaddress.IPv4Address(private_ip)
    if not any(address in ipaddress.IPv4Network(network) for network in
               ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('private issuer address must be RFC1918 IPv4')
    return name,name+':'+str(address)
