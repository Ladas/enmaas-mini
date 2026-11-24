"""Realm identities and client boundaries are independent of deployment tooling."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

PATH = Path(__file__).resolve().parents[1] / 'realm.py'
spec = importlib.util.spec_from_file_location('issuer_realm', PATH)
realm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(realm)


class Realm(unittest.TestCase):
    def test_immutable_ids_client_scopes_and_private_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            realm.configure(root)
            identities = json.loads((root/'identities.json').read_text())
            secrets = json.loads((root/'credentials.json').read_text())
            config = json.loads((root/'realm.json').read_text())
            self.assertEqual(set(identities), {'admin', 'alice', 'bob'})
            self.assertEqual(len(set(identities.values())), 3)
            self.assertEqual(len(set(secrets.values())), len(secrets))
            for user in config['users']:
                self.assertEqual(str(uuid.UUID(user['id'])), identities[user['username']])
                self.assertEqual(user['groups'], ['/observability-admin'] if user['username']=='admin' else [])
            clients = {client['clientId']: client for client in config['clients']}
            self.assertEqual(set(clients), {'enmaas-mini', 'observability'})
            for client in clients.values():
                self.assertFalse(client['publicClient'])
                self.assertFalse(client['directAccessGrantsEnabled'])
                self.assertTrue(client['standardFlowEnabled'])
                self.assertFalse(any('*' in value for value in client['redirectUris']))
            mapping = clients['enmaas-mini']['protocolMappers'][0]['config']
            self.assertEqual(mapping['user.attribute'], 'id')
            self.assertEqual(mapping['claim.name'], 'rhatUUID')
            self.assertEqual(clients['enmaas-mini']['attributes']['pkce.code.challenge.method'], 'S256')
            for path in root.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            snapshot = {path.name: path.read_bytes() for path in root.iterdir()}
            with self.assertRaises(FileExistsError):
                realm.configure(root)
            self.assertEqual(snapshot, {path.name: path.read_bytes() for path in root.iterdir()})

    def test_configuration_has_no_dependency_on_runtime_or_monitoring(self):
        imports = []
        for node in ast.walk(ast.parse(PATH.read_text())):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertEqual(set(imports), {'json', 'pathlib', 'secrets', 'uuid'})


if __name__ == '__main__':
    unittest.main()
