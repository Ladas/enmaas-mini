"""Shared private realm inputs for isolated identity and local integration tests."""
import json
from pathlib import Path
import secrets
import uuid

HERE = Path(__file__).resolve().parent
IMAGES = {name: entry['image'] for name, entry in json.loads((HERE/'images.json').read_text()).items()}


def write(root, name, value):
    path = root/name
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2)+'\n')
    path.chmod(0o600)


def configure(root, authorization_test=False):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    if (root/'credentials.json').exists():
        raise FileExistsError('Existing lab credentials; use start to resume, never overwrite them')
    credentials = {key: secrets.token_urlsafe(30) for key in ('admin', 'alice', 'bob', 'db', 'oidc', 'gateway_oidc')}
    write(root, 'credentials.json', credentials)
    identities = {name: str(uuid.uuid4()) for name in ('admin', 'alice', 'bob')}
    write(root, 'identities.json', identities)
    users = []
    for name in ('admin', 'alice', 'bob'):
        users.append({'id': identities[name], 'username': name, 'email': f'{name}@example.test', 'emailVerified': True,
                      'enabled': True, 'firstName': name.title(), 'lastName': 'Lab',
                      'groups': ['/observability-admin'] if name == 'admin' else [],
                      'credentials': [{'type': 'password', 'value': credentials[name], 'temporary': False}]})
    write(root, 'realm.json', {
        'realm': 'enmaas-lab', 'enabled': True, 'sslRequired': 'all',
        'registrationAllowed': False, 'resetPasswordAllowed': False,
        'bruteForceProtected': True, 'permanentLockout': False, 'maxTemporaryLockouts': 0,
        'failureFactor': 5, 'waitIncrementSeconds': 60,
        'minimumQuickLoginWaitSeconds': 60, 'quickLoginCheckMilliSeconds': 1000,
        'maxFailureWaitSeconds': 900, 'maxDeltaTimeSeconds': 43200,
        'accessTokenLifespan': 60, 'ssoSessionIdleTimeout': 300, 'ssoSessionMaxLifespan': 1800,
        'groups': [{'name': 'observability-admin'}], 'users': users,
        'clients': [{'clientId': 'observability', 'secret': credentials['oidc'],
                     'publicClient': False, 'standardFlowEnabled': True,
                     'directAccessGrantsEnabled': False,
                     'redirectUris': ['https://localhost:19443/oauth2/callback'],
                     'webOrigins': ['https://localhost:19443'],
                     'protocolMappers': [{'name': 'groups', 'protocol': 'openid-connect',
                        'protocolMapper': 'oidc-group-membership-mapper',
                        'config': {'claim.name': 'groups', 'full.path': 'true',
                                   'id.token.claim': 'true', 'access.token.claim': 'true',
                                   'userinfo.token.claim': 'true'}}]}]})
    realm = json.loads((root/'realm.json').read_text())
    realm['clients'].append({
        'clientId': 'enmaas-mini', 'secret': credentials['gateway_oidc'],
        'publicClient': False, 'standardFlowEnabled': True,
        'directAccessGrantsEnabled': False,
        'redirectUris': ['https://localhost:28443/oauth/callback'],
        'webOrigins': ['https://localhost:28443'],
        'attributes': {'pkce.code.challenge.method': 'S256',
                       'post.logout.redirect.uris': 'https://localhost:28443/login'},
        # Map Keycloak's immutable user ID, never email or a user-editable attribute.
        'protocolMappers': [{
            'name': 'metering-identity', 'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-property-mapper',
            'config': {'user.attribute': 'id', 'claim.name': 'rhatUUID',
                       'jsonType.label': 'String', 'id.token.claim': 'true',
                       'access.token.claim': 'true', 'userinfo.token.claim': 'true'}}]})
    if authorization_test:
        # Explicitly opt in only for a disposable local realm. RHEL generation
        # never enables this client; the credential stays in private lab state.
        credentials['authorization_test']=secrets.token_urlsafe(32)
        write(root, 'credentials.json', credentials)
        realm['clients'].append({
            'clientId':'lab-authorization-test', 'secret':credentials['authorization_test'],
            'publicClient':False, 'serviceAccountsEnabled':True,
            'defaultClientScopes':['kc-admin-api'],
            'standardFlowEnabled':False, 'directAccessGrantsEnabled':False})
        realm['users'].append({
            'username':'service-account-lab-authorization-test','enabled':True,
            'serviceAccountClientId':'lab-authorization-test',
            'clientRoles':{'realm-management':['manage-users','query-groups','query-users']}})
    write(root, 'realm.json', realm)
    write(root, 'db-password', credentials['db'])
