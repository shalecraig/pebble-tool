# Authentication System

The Pebble Tool uses GitHub OAuth 2.0 for user authentication, primarily for CloudPebble proxy access.

## Overview

**Authentication Method:** GitHub OAuth 2.0
**Token Storage:** Local filesystem (plaintext)
**Primary Use:** CloudPebble proxy connection, emulator OAuth tokens

**Files:**
- `pebble_tool/account.py` - Core authentication logic
- `pebble_tool/commands/account.py` - Login/logout commands

## GitHub OAuth Flow

### OAuth Configuration

**File:** `pebble_tool/account.py:26-36`

```python
SDK_CLIENT_ID = os.getenv("PEBBLE_OAUTH_APP_ID", "Iv23likC9qHcKRPfqCRu")
SDK_CLIENT_SECRET = os.getenv("PEBBLE_OAUTH_APP_SECRET", "f7a3280b328d14fae132c5f97b4f151f13936f4f")

flow = OAuth2WebServerFlow(
    client_id=SDK_CLIENT_ID,
    client_secret=SDK_CLIENT_SECRET,
    redirect_uri="https://cloud.repebble.com/githubAuth",
    scope="profile",
    auth_uri=AUTHORIZE_URI,  # https://github.com/login/oauth/authorize
    token_uri=TOKEN_URI      # https://github.com/login/oauth/access_token
)
```

### Login Command Flow

**Entry Point:** `pebble_tool/commands/account.py:12-19`

```python
class LogInCommand(BaseCommand):
    command = 'login'

    def __call__(self, args):
        account = get_default_account()
        if hasattr(args, 'token') and args.token:
            account.login_with_token(args.token)  # Direct token
        else:
            account.login(args)  # OAuth flow
```

### OAuth Flow Implementation

**Function:** `_run_flow()` (account.py:38-64)

**Steps:**

1. **Start Local Server** (lines 39-40)
   ```python
   httpd = tools.ClientRedirectServer(("localhost", 60000),
                           tools.ClientRedirectHandler)
   ```
   - HTTP server on `localhost:60000` for OAuth callback

2. **Generate Authorization URL** (line 41)
   ```python
   authorize_url = flow.step1_get_authorize_url()
   ```
   - Points to `https://github.com/login/oauth/authorize`

3. **Open Browser** (lines 42-43)
   ```python
   webbrowser.open(authorize_url, new=1, autoraise=True)
   ```

4. **Wait for Callback** (lines 45-53)
   ```python
   httpd.handle_request()
   if 'error' in httpd.query_params:
       sys.exit('Authentication request was rejected.')
   if 'code' in httpd.query_params:
       code = httpd.query_params['code']
   ```
   - Server waits for GitHub redirect with authorization code

5. **Exchange Code for Token** (lines 55-58)
   ```python
   credential = flow.step2_exchange(code)
   ```
   - Exchanges code for access token via GitHub API

6. **Store Credentials** (lines 60-62)
   ```python
   storage.put(credential)
   credential.set_store(storage)
   ```

### Direct Token Login

**Function:** `login_with_token()` (account.py:136-149)

```python
def login_with_token(self, access_token):
    creds = OAuth2Credentials(
        access_token=access_token,
        client_id=SDK_CLIENT_ID,
        client_secret=SDK_CLIENT_SECRET,
        refresh_token=None,
        token_expiry=None,
        token_uri=TOKEN_URI,
        user_agent=None
    )
    creds = self._set_expiration_to_long_time(creds)
    self.storage.put(creds)
    self._user_info = self._get_user_info()
```

## Token Storage

### Storage Location

**Linux:** `~/.pebble-sdk/oauth/`
**macOS:** `~/Library/Application Support/Pebble SDK/oauth/`

**Files:**
- `oauth_storage` - OAuth2 credentials (access token, client ID, etc.)
- `user_info` - Cached GitHub user information

### Account Class

**File:** `pebble_tool/account.py:67-72`

```python
class Account:
    def __init__(self, persistent_dir):
        self.persistent_dir = persistent_dir
        self.storage = Storage(os.path.join(persistent_dir, 'oauth_storage'))
        self._user_info = None
        self._get_user_info()
```

### Token Retrieval

```python
def get_credentials(self):
    return self.storage.get()

def get_access_token(self):
    creds = self.get_credentials()
    token_info = creds.get_access_token()
    return token_info.access_token

bearer_token = property(get_access_token)
```

### Login Status Check

```python
@property
def is_logged_in(self):
    if os.path.isfile(os.path.join(self.persistent_dir, 'oauth_storage')) and self.storage.get():
        return True
    return False
```

## Token Expiration Handling

**Function:** `_set_expiration_to_long_time()` (account.py:119-128)

```python
def _set_expiration_to_long_time(self, creds):
    cred_str = creds.to_json()
    cred_json = json.loads(cred_str)

    # In case it might have an expiration
    if cred_json['token_expiry'] is not None:
        return creds

    cred_json['token_expiry'] = '2100-01-01T00:00:01Z'
    cred_new_json = json.dumps(cred_json)
    return Credentials.new_from_json(cred_new_json)
```

**Purpose:** Sets expiration to year 2100 for tokens without expiration date

## User Information

**Function:** `_get_user_info()` (account.py:155-178)

```python
def _get_user_info(self):
    if self._user_info is not None:
        return self._user_info

    if not self.is_logged_in:
        return None

    file_path = self._user_info_path
    try:
        with open(file_path) as f:
            return json.load(f)
    except (IOError, ValueError):
        with open(file_path, 'w') as f:
            result = requests.get(ME_URI, headers={
                'Authorization': f'Bearer {self.get_access_token()}'
            })
            result.raise_for_status()
            account_info = result.json()
            stored_info = {
                'id': account_info['id'],
                'name': account_info['name'],
                'legacy_id': None
            }
            json.dump(stored_info, f)
            self._user_info = stored_info
            return self._user_info
```

**API Endpoint:** `https://api.github.com/user`

**Flow:**
1. Check in-memory cache
2. Try to load from `user_info` file
3. If not found, make API request with Bearer token
4. Cache response to file and memory

## Logout Flow

**File:** `pebble_tool/commands/account.py:37-43`

```python
class LogOutCommand(BaseCommand):
    command = 'logout'

    def __call__(self, args):
        account = get_default_account()
        if account.is_logged_in:
            account.logout()
        else:
            print("You aren't logged in anyway.")
```

**Function:** `logout()` (account.py:151-153)

```python
def logout(self):
    self.storage.delete()  # Deletes oauth_storage file
    os.unlink(self._user_info_path)  # Deletes user_info file
```

## CloudPebble Proxy Integration

**File:** `pebble_tool/sdk/cloudpebble.py`

### Connection Flow

```python
def connect(self):
    account = get_default_account()
    if not account.is_logged_in:
        raise ToolError("You must be logged in to use CloudPebble connection.")

    self.ws = websocket.create_connection(CP_TRANSPORT_HOST)
    self._authenticate()
    self._wait_for_phone()
    self._phone_connected = True
```

**Proxy Host:** `wss://cloudpebble-proxy.repebble.com/tool`

### Authentication Process

```python
def _authenticate(self):
    oauth = get_default_account().bearer_token
    self.send_packet(
        WebSocketProxyAuthenticationRequest(token=oauth),
        target=MessageTargetPhone()
    )
    target, packet = self.read_packet()
    if isinstance(packet, WebSocketProxyAuthenticationResponse):
        if packet.status != WebSocketProxyAuthenticationResponse.StatusCode.Success:
            raise ToolError("Failed to authenticate to CloudPebble proxy.")
```

**Steps:**
1. Retrieve OAuth bearer token
2. Send `WebSocketProxyAuthenticationRequest` with token
3. Wait for `WebSocketProxyAuthenticationResponse`
4. Verify status is Success

### Phone Connection Wait

```python
def _wait_for_phone(self):
    print("Waiting for phone to connect...")
    target, packet = self.read_packet()
    if isinstance(packet, WebSocketProxyConnectionStatusUpdate):
        if packet.status == WebSocketProxyConnectionStatusUpdate.StatusCode.Connected:
            print("Connected.")
            return
    raise ToolError("Unexpected message when waiting for phone connection.")
```

## Emulator OAuth Integration

**File:** `pebble_tool/sdk/emulator.py:412-439`

```python
def _spawn_pypkjs(self):
    command = [
        sys.executable, "-m", "pypkjs",
        "--qemu", f"localhost:{self.qemu_port}",
        "--port", str(self.pypkjs_port),
        "--persist", get_sdk_persist_dir(self.platform, self.version),
        "--layout", layout_file,
        '--debug',
    ]

    account = get_default_account()
    if account.is_logged_in:
        command.extend(['--oauth', account.bearer_token])
```

**Purpose:** Pass OAuth token to pypkjs for authenticated API calls from emulated apps

## Environment Variable Overrides

```python
AUTH_SERVER = os.getenv("PEBBLE_OAUTH_SERVER", "https://github.com")
API_SERVER = os.getenv("PEBBLE_OAUTH_API_SERVER", "https://api.github.com")
SDK_CLIENT_ID = os.getenv("PEBBLE_OAUTH_APP_ID", "Iv23likC9qHcKRPfqCRu")
SDK_CLIENT_SECRET = os.getenv("PEBBLE_OAUTH_APP_SECRET", "...")
```

## Security Considerations

### Strengths

1. **OAuth 2.0 Standard** - Industry-standard GitHub OAuth
2. **No Password Storage** - Only OAuth tokens stored
3. **Secure File Permissions** - oauth2client.file.Storage sets proper permissions
4. **HTTPS/WSS** - All communications encrypted

### Weaknesses

1. **Client Secret in Source** - Hardcoded (acceptable for native apps per OAuth spec)
2. **No Token Encryption** - Tokens stored in plaintext
3. **Long Expiration** - Set to year 2100 (tokens valid extremely long time)
4. **No Token Revocation** - Logout only deletes local files
5. **Local HTTP Server** - OAuth callback uses localhost (minimal risk)
6. **No CSRF Protection** - OAuth flow doesn't use state parameter
7. **User Info Caching** - Cached indefinitely in plaintext

## Command Examples

```bash
# Login with OAuth flow
pebble login

# Login with existing token
pebble login --token ghp_xxxxxxxxxxxxx

# Check login status
pebble login  # Shows if already logged in

# Logout
pebble logout

# Use CloudPebble proxy (requires login)
pebble logs --cloudpebble
```

## Complete OAuth Flow Diagram

```
User runs 'pebble login'
         ↓
LogInCommand.__call__()
         ↓
Account.login(args)
         ↓
_run_flow(flow, storage, args)
         ↓
Start HTTP server on localhost:60000
         ↓
Generate authorize_url
         ↓
Open browser to GitHub OAuth
    https://github.com/login/oauth/authorize
    ?client_id=Iv23likC9qHcKRPfqCRu
    &redirect_uri=https://cloud.repebble.com/githubAuth
    &scope=profile
         ↓
User authenticates with GitHub
         ↓
GitHub redirects to localhost:60000/?code=<code>
         ↓
httpd.handle_request() receives callback
         ↓
Extract authorization code
         ↓
flow.step2_exchange(code)
    POST https://github.com/login/oauth/access_token
    with client_id, client_secret, code
         ↓
Receive access_token from GitHub
         ↓
_set_expiration_to_long_time(creds)
         ↓
storage.put(credential)
    Saves to ~/.pebble-sdk/oauth/oauth_storage
         ↓
_get_user_info()
    GET https://api.github.com/user
    with Authorization: Bearer <token>
         ↓
Cache user info to ~/.pebble-sdk/oauth/user_info
         ↓
Print "Authentication successful."
```

## Summary

The authentication system provides:
- **GitHub OAuth** - Standard OAuth 2.0 flow
- **CloudPebble Integration** - Proxy authentication
- **Emulator Support** - Token passing to pypkjs
- **Simple Storage** - Local filesystem (plaintext)
- **User Info Caching** - GitHub user data persistence

**Trade-offs:**
- Convenience (long-lived tokens, local storage) vs Security (plaintext, no encryption)
- Acceptable for developer tool, but could be improved with OS keychain integration
