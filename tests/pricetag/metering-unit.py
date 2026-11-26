#!/usr/bin/env python3
"""Run PriceTag Go tests with isolated PostgreSQL, without deployment credentials."""
import argparse
from pathlib import Path
import platform
import subprocess
import time
import uuid

# 17.12-fips pinned per architecture: registry.access.redhat.com fails
# manifest-list pulls with unauthorized blob errors on older Podman (CI's
# Ubuntu 24.04 ships 4.9.3). 'arm64' mirrors 'aarch64' for macOS hosts.
POSTGRES_ARCHES = {
    'x86_64': 'registry.access.redhat.com/hi/postgresql@sha256:52e9435300b2fe89f8534e03e86d54179b86a1a4ca29a9c4bd426b000958a4b9',
    'aarch64': 'registry.access.redhat.com/hi/postgresql@sha256:f097ed322c237e6f955ce24fbe503a4cd46b58ce9cde1677aca2586ebd08bf2c',
    'arm64': 'registry.access.redhat.com/hi/postgresql@sha256:f097ed322c237e6f955ce24fbe503a4cd46b58ce9cde1677aca2586ebd08bf2c',
}
POSTGRES = POSTGRES_ARCHES[platform.machine()]
GOLANG = 'docker.io/library/golang@sha256:0f063af2d465d8dcae54cce04278ada488b96f77b42449c8d071e47d016cc65a'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if not (source / 'go.mod').is_file():
        parser.error('source must be the checked-out PriceTag repository')
    name = 'pricetag-unit-' + uuid.uuid4().hex[:12]
    database, runner = name + '-db', name + '-go'
    network_created = database_created = False

    def run(*command, **kwargs):
        return subprocess.run(['podman', *map(str, command)], check=True, **kwargs)

    try:
        run('network', 'create', name)
        network_created = True
        # Synthetic test credential; PostgreSQL has no host-published port.
        run('run', '-d', '--name', database, '--network', name,
            '--network-alias', 'test-db', '-e', 'POSTGRES_PASSWORD=synthetic-test-only', POSTGRES)
        database_created = True
        for _ in range(60):
            ready = subprocess.run(['podman', 'exec', database, 'pg_isready', '-U', 'postgres'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('isolated test PostgreSQL did not become ready')
        run('run', '--rm', '--name', runner, '--network', name,
            '--security-opt', 'no-new-privileges',
            '-e', 'DATABASE_URL=postgres://postgres:synthetic-test-only@test-db:5432/postgres?sslmode=disable',
            '-v', str(source) + ':/src:ro,Z', '-w', '/src', GOLANG,
            'go', 'test', './...', timeout=900)
    finally:
        # Only these uniquely named test containers/network can be removed.
        subprocess.run(['podman', 'rm', '-f', '--ignore', runner], check=False)
        if database_created:
            run('rm', '-f', database)
        if network_created:
            run('network', 'rm', name)


if __name__ == '__main__':
    main()
