"""
SimpleFIN Bridge Integration
Connects to SimpleFIN Bridge (https://www.simplefin.org/protocol.html)
to automatically fetch account balances from financial institutions.

Flow:
1. User gets a setup token from https://bridge.simplefin.org/
2. App claims the token (one-time POST) to get a permanent access URL
3. App uses access URL to fetch account data on demand
"""

import base64
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class SimplefinOrg:
    """Institution/organization info from SimpleFIN."""
    name: str
    domain: str | None = None
    sfin_url: str | None = None


@dataclass
class SimplefinTransaction:
    """A transaction from SimpleFIN."""
    id: str
    posted: int  # Unix timestamp
    amount: float
    description: str
    payee: str | None = None
    memo: str | None = None


@dataclass
class SimplefinAccount:
    """Account info from SimpleFIN."""
    id: str
    name: str
    org: SimplefinOrg
    currency: str
    balance: float
    available_balance: float | None = None
    balance_date: int | None = None  # Unix timestamp
    transactions: list[SimplefinTransaction] = field(default_factory=list)


@dataclass
class SimplefinSyncResult:
    """Result of a balance sync operation."""
    success: bool
    accounts_updated: int = 0
    accounts_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    details: list[dict] = field(default_factory=list)


class SimplefinClient:
    """Client for the SimpleFIN Bridge protocol."""

    @staticmethod
    def claim_setup_token(setup_token: str) -> str:
        """
        Exchange a one-time setup token for a permanent access URL.

        The setup token is Base64-encoded. Decoding it yields a claim URL.
        We POST to that URL (with an empty body) to receive the access URL.

        IMPORTANT: We use http.client instead of urllib because urllib
        silently converts POST→GET on 301/302 redirects, which causes
        the SimpleFIN server to return 403 (it requires POST).

        Args:
            setup_token: Base64-encoded setup token from SimpleFIN Bridge

        Returns:
            Access URL (with embedded credentials) for fetching account data

        Raises:
            ValueError: If the token is invalid or claim fails
        """
        import logging
        log = logging.getLogger('simplefin')

        # Strip whitespace, newlines, and any surrounding quotes
        cleaned_token = setup_token.strip().strip('"').strip("'").replace('\n', '').replace('\r', '')

        try:
            # Decode the setup token to get the claim URL
            claim_url = base64.b64decode(cleaned_token).decode('utf-8').strip()
        except Exception:
            raise ValueError("Invalid setup token: could not Base64-decode. "
                             "Make sure you're pasting the full token from SimpleFIN Bridge.")

        if not claim_url.startswith('http'):
            raise ValueError(f"Invalid setup token: decoded URL doesn't look like a valid URL. "
                             f"Decoded to: {claim_url[:80]}")

        log.info(f"Claiming SimpleFIN token, decoded URL host: "
                 f"{urllib.parse.urlparse(claim_url).hostname}")

        # POST to the claim URL to get the access URL
        # Use http.client directly to avoid urllib redirect issues (POST→GET conversion)
        import ssl
        from http.client import HTTPSConnection, HTTPConnection

        parsed = urllib.parse.urlparse(claim_url)
        host = parsed.hostname
        port = parsed.port
        path = parsed.path
        if parsed.query:
            path += '?' + parsed.query
        scheme = parsed.scheme

        try:
            # Follow up to 5 redirects, preserving POST method
            max_redirects = 5
            current_url = claim_url
            for redirect_num in range(max_redirects):
                if scheme == 'https':
                    ssl_ctx = ssl.create_default_context()
                    conn = HTTPSConnection(host, port or 443, timeout=30, context=ssl_ctx)
                else:
                    conn = HTTPConnection(host, port or 80, timeout=30)

                log.debug(f"POST {scheme}://{host}{path} (attempt {redirect_num + 1})")

                conn.request('POST', path, body=b'', headers={
                    'Content-Length': '0',
                    'Host': host,
                    'Accept': '*/*',
                })
                response = conn.getresponse()
                status = response.status
                response_headers = dict(response.getheaders())
                body = response.read().decode('utf-8', errors='replace').strip()
                conn.close()

                log.debug(f"Response: HTTP {status}")

                # Handle redirects (301, 302, 303, 307, 308) - keep POST method
                if status in (301, 302, 303, 307, 308):
                    location = response_headers.get('Location') or response_headers.get('location')
                    if not location:
                        raise ValueError(f"Redirect (HTTP {status}) but no Location header")
                    log.info(f"Following redirect {status} -> {location}")
                    # Resolve relative URLs
                    location = urllib.parse.urljoin(current_url, location)
                    parsed = urllib.parse.urlparse(location)
                    host = parsed.hostname
                    port = parsed.port
                    path = parsed.path
                    scheme = parsed.scheme
                    if parsed.query:
                        path += '?' + parsed.query
                    current_url = location
                    continue
                break
            else:
                raise ValueError("Too many redirects while claiming SimpleFIN token")
        except ssl.SSLCertVerificationError as e:
            raise ValueError(
                f"SSL certificate verification failed for {host}: {e}. "
                f"This may be caused by a corporate proxy or firewall."
            )
        except ssl.SSLError as e:
            raise ValueError(f"SSL error connecting to SimpleFIN Bridge ({host}): {e}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to connect to SimpleFIN Bridge ({host}): {e}")

        if status == 403:
            raise ValueError(
                f"SimpleFIN returned 403 Forbidden. "
                f"Per the SimpleFIN protocol, this means the token does not exist "
                f"or has already been claimed. "
                f"Try generating a new setup token from SimpleFIN Bridge. "
                f"(Server said: {body or 'empty'})"
            )
        elif status >= 400:
            raise ValueError(f"Failed to claim token: HTTP {status} - {body or 'no details'}")

        access_url = body

        if not access_url or not access_url.startswith('http'):
            raise ValueError("Received invalid access URL from SimpleFIN Bridge. "
                             f"HTTP {status}, response was: "
                             f"{access_url[:100] if access_url else 'empty'}")

        log.info("SimpleFIN token claimed successfully")
        return access_url

    @staticmethod
    def fetch_accounts(access_url: str, start_date: int = None) -> list[SimplefinAccount]:
        """
        Fetch account data from SimpleFIN Bridge.

        Uses http.client directly (same as claim_setup_token) to avoid
        urllib issues with SSL, redirects, and auth header stripping.

        Args:
            access_url: The permanent access URL (with embedded user:pass)
            start_date: Unix timestamp — if provided, fetch transactions from this date

        Returns:
            List of SimplefinAccount objects

        Raises:
            ValueError: If the request fails
        """
        import logging
        import ssl
        import time
        from http.client import HTTPSConnection, HTTPConnection

        log = logging.getLogger('simplefin')

        # Parse the access URL to extract auth and build the accounts endpoint
        parsed = urllib.parse.urlparse(access_url)

        # Build the accounts path
        accounts_path = parsed.path.rstrip('/') + '/accounts'

        # Add query parameters
        query_params = {}
        if parsed.query:
            query_params = dict(urllib.parse.parse_qsl(parsed.query))
        if start_date is not None:
            query_params['start-date'] = str(start_date)
        # Always set end-date to current time to ensure SimpleFIN returns
        # the latest available data rather than potentially cached results
        query_params['end-date'] = str(int(time.time()))
        query_string = urllib.parse.urlencode(query_params) if query_params else ''

        # Set up Basic auth from the URL credentials
        username = parsed.username or ''
        password = parsed.password or ''
        auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()

        host = parsed.hostname
        port = parsed.port
        scheme = parsed.scheme
        path = accounts_path
        if query_string:
            path += '?' + query_string

        log.info(f"Fetching SimpleFIN accounts from {host}")

        try:
            # Follow redirects while preserving auth, up to 5 hops
            current_url = f"{scheme}://{host}{':' + str(port) if port else ''}{path}"
            max_redirects = 5
            for redirect_num in range(max_redirects):
                if scheme == 'https':
                    ssl_ctx = ssl.create_default_context()
                    conn = HTTPSConnection(host, port or 443, timeout=30, context=ssl_ctx)
                else:
                    conn = HTTPConnection(host, port or 80, timeout=30)

                log.debug(f"GET {scheme}://{host}{path} (attempt {redirect_num + 1})")

                conn.request('GET', path, headers={
                    'Authorization': f'Basic {auth_string}',
                    'Accept': 'application/json',
                    'Host': host,
                })
                response = conn.getresponse()
                status = response.status
                response_headers = dict(response.getheaders())
                body = response.read().decode('utf-8', errors='replace')
                conn.close()

                log.debug(f"Response: HTTP {status}")

                # Handle redirects — preserve GET and auth header
                if status in (301, 302, 303, 307, 308):
                    location = response_headers.get('Location') or response_headers.get('location')
                    if not location:
                        raise ValueError(f"Redirect (HTTP {status}) but no Location header")
                    log.info(f"Following redirect {status} -> {location}")
                    location = urllib.parse.urljoin(current_url, location)
                    redir_parsed = urllib.parse.urlparse(location)
                    host = redir_parsed.hostname
                    port = redir_parsed.port
                    scheme = redir_parsed.scheme
                    path = redir_parsed.path
                    if redir_parsed.query:
                        path += '?' + redir_parsed.query
                    current_url = location
                    continue
                break
            else:
                raise ValueError("Too many redirects fetching SimpleFIN accounts")
        except ssl.SSLCertVerificationError as e:
            raise ValueError(
                f"SSL certificate verification failed for {host}: {e}. "
                f"This may be caused by a corporate proxy or firewall."
            )
        except ssl.SSLError as e:
            raise ValueError(f"SSL error connecting to SimpleFIN Bridge ({host}): {e}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to fetch accounts: {e}")

        if status == 401 or status == 403:
            raise ValueError("SimpleFIN access denied. You may need to reconnect.")
        if status >= 400:
            raise ValueError(f"Failed to fetch accounts: HTTP {status} - {body[:200] if body else 'no details'}")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON response from SimpleFIN Bridge (HTTP {status})")

        # Parse the account set response
        accounts = []
        raw_accounts = data.get('accounts', [])

        # Check for SimpleFIN-level errors (e.g., institution connection issues)
        sfin_errors = data.get('errors', [])
        if sfin_errors:
            log.warning(f"SimpleFIN reported {len(sfin_errors)} error(s):")
            for err in sfin_errors:
                log.warning(f"  - {err}")

        log.info(f"Received {len(raw_accounts)} accounts from SimpleFIN")
        for raw in raw_accounts:
            org_data = raw.get('org', {})
            org = SimplefinOrg(
                name=org_data.get('name', 'Unknown'),
                domain=org_data.get('domain'),
                sfin_url=org_data.get('sfin-url'),
            )
            account = SimplefinAccount(
                id=raw.get('id', ''),
                name=raw.get('name', 'Unknown'),
                org=org,
                currency=raw.get('currency', 'USD'),
                balance=float(raw.get('balance', 0)),
                available_balance=float(raw['available-balance']) if 'available-balance' in raw else None,
                balance_date=raw.get('balance-date'),
            )
            # Parse transactions if present
            for raw_txn in raw.get('transactions', []):
                txn = SimplefinTransaction(
                    id=raw_txn.get('id', ''),
                    posted=raw_txn.get('posted', 0),
                    amount=float(raw_txn.get('amount', 0)),
                    description=raw_txn.get('description', ''),
                    payee=raw_txn.get('payee'),
                    memo=raw_txn.get('memo'),
                )
                account.transactions.append(txn)
            accounts.append(account)

        return accounts

    @staticmethod
    def sync_balances(access_url: str, mappings: dict, manager) -> SimplefinSyncResult:
        """
        Fetch accounts from SimpleFIN and update mapped local account balances.

        Args:
            access_url: SimpleFIN access URL
            mappings: Dict mapping simplefin_account_id -> {bank_name, account_name, account_type}
            manager: FinanceManager instance

        Returns:
            SimplefinSyncResult with details of what was updated
        """
        result = SimplefinSyncResult(success=True)

        try:
            import logging
            import time
            log = logging.getLogger('simplefin')
            # Request data from the last 24 hours to ensure SimpleFIN returns
            # fresh balances rather than potentially stale cached data.
            start_ts = int(time.time()) - 86400
            sfin_accounts = SimplefinClient.fetch_accounts(access_url, start_date=start_ts)
        except ValueError as e:
            return SimplefinSyncResult(success=False, errors=[str(e)])

        log.info(f"Syncing {len(sfin_accounts)} SimpleFIN accounts against {len(mappings)} mappings")

        for sfin_acc in sfin_accounts:
            mapping = mappings.get(sfin_acc.id)
            if not mapping:
                result.accounts_skipped += 1
                continue

            bank_name = mapping['bank_name']
            account_name = mapping['account_name']
            account_type = mapping['account_type']
            new_balance = sfin_acc.balance

            # Find the bank
            bank = next((b for b in manager.banks if b.name == bank_name), None)
            if not bank:
                result.errors.append(f"Bank '{bank_name}' not found for SimpleFIN account '{sfin_acc.name}'")
                continue

            prev_balance = 0.0
            try:
                if account_type == 'credit':
                    acc = bank.credit_accounts.get(account_name)
                    if not acc:
                        result.errors.append(f"Credit account '{account_name}' not found")
                        continue
                    prev_balance = acc.balance
                    # SimpleFIN reports credit balances as negative (amount owed)
                    # Our system stores credit balances as positive (amount owed)
                    new_balance = abs(new_balance)
                elif account_type == 'mortgage':
                    acc = bank.mortgage_accounts.get(account_name)
                    if not acc:
                        result.errors.append(f"Mortgage '{account_name}' not found")
                        continue
                    prev_balance = acc.current_principal
                    new_balance = abs(new_balance)
                elif account_type == 'heloc':
                    acc = bank.heloc_accounts.get(account_name)
                    if not acc:
                        result.errors.append(f"HELOC account '{account_name}' not found")
                        continue
                    prev_balance = acc.balance
                    # SimpleFIN reports HELOC balances as negative (amount owed)
                    # Our system stores HELOC balances as positive (amount owed)
                    new_balance = abs(new_balance)
                else:
                    acc = bank.accounts.get(account_name)
                    if not acc:
                        result.errors.append(f"Account '{account_name}' not found")
                        continue
                    prev_balance = acc.balance

                # Skip if balance hasn't changed (within rounding tolerance)
                log.debug(f"  {bank_name}/{account_name} ({account_type}): "
                          f"SimpleFIN={sfin_acc.balance} -> adjusted={new_balance}, "
                          f"local={prev_balance}, "
                          f"balance_date={sfin_acc.balance_date}")
                if abs(new_balance - prev_balance) < 0.005:
                    result.accounts_skipped += 1
                    result.details.append({
                        'account': f"{bank_name}/{account_name}",
                        'previous': prev_balance,
                        'new': new_balance,
                        'source': f"{sfin_acc.org.name}/{sfin_acc.name}",
                        'status': 'unchanged',
                    })
                    continue

                # Actually update the balance
                if account_type == 'credit':
                    bank.update_credit_balance(account_name, new_balance)
                elif account_type == 'mortgage':
                    acc.current_principal = new_balance
                elif account_type == 'heloc':
                    acc.balance = new_balance
                else:
                    bank.update_account_balance(account_name, new_balance)

                # Record balance history only for actual changes
                _record_balance_history(
                    bank_name, account_name, account_type,
                    new_balance, prev_balance,
                    f"SimpleFIN sync: {sfin_acc.org.name} / {sfin_acc.name}"
                )

                result.accounts_updated += 1
                result.details.append({
                    'account': f"{bank_name}/{account_name}",
                    'previous': prev_balance,
                    'new': new_balance,
                    'source': f"{sfin_acc.org.name}/{sfin_acc.name}",
                    'status': 'updated',
                })

            except Exception as e:
                result.errors.append(f"Error updating {bank_name}/{account_name}: {e}")

        # Save all changes
        if result.accounts_updated > 0:
            manager.save_to_database()

        return result


def _record_balance_history(bank_name: str, account_name: str, account_type: str,
                            new_balance: float, prev_balance: float, notes: str):
    """Record a balance update in the history table."""
    try:
        from models.database import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_name TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    balance REAL NOT NULL,
                    previous_balance REAL,
                    recorded_at TEXT NOT NULL,
                    notes TEXT
                )
            """))
            session.execute(text("""
                INSERT INTO balance_history (bank_name, account_name, account_type, balance, previous_balance, recorded_at, notes)
                VALUES (:bn, :an, :at, :bal, :prev, :ts, :notes)
            """), {
                "bn": bank_name, "an": account_name, "at": account_type,
                "bal": new_balance, "prev": prev_balance,
                "ts": datetime.now(timezone.utc).isoformat(),
                "notes": notes,
            })
            session.commit()
        finally:
            session.close()
    except Exception:
        pass


# ==================== Database Helpers ====================

def get_simplefin_connection() -> dict | None:
    """Get the stored SimpleFIN connection (access_url + metadata)."""
    try:
        from models.database import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='simplefin_connection'"
            )).fetchone()
            if not result:
                return None
            row = session.execute(text(
                "SELECT access_url, created_at, last_sync_at FROM simplefin_connection LIMIT 1"
            )).fetchone()
            if not row:
                return None
            return {
                'access_url': row[0],
                'created_at': row[1],
                'last_sync_at': row[2],
            }
        finally:
            session.close()
    except Exception:
        return None


def save_simplefin_connection(access_url: str):
    """Store the SimpleFIN access URL in the database."""
    from models.database import get_session
    from sqlalchemy import text
    session = get_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS simplefin_connection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_sync_at TEXT
            )
        """))
        # Clear any existing connection
        session.execute(text("DELETE FROM simplefin_connection"))
        session.execute(text("""
            INSERT INTO simplefin_connection (access_url, created_at)
            VALUES (:url, :ts)
        """), {"url": access_url, "ts": datetime.now(timezone.utc).isoformat()})
        session.commit()
    finally:
        session.close()


def update_simplefin_last_sync():
    """Update the last_sync_at timestamp."""
    try:
        from models.database import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            session.execute(text(
                "UPDATE simplefin_connection SET last_sync_at = :ts"
            ), {"ts": datetime.now(timezone.utc).isoformat()})
            session.commit()
        finally:
            session.close()
    except Exception:
        pass


def remove_simplefin_connection():
    """Remove the SimpleFIN connection and all mappings."""
    try:
        from models.database import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            session.execute(text("DROP TABLE IF EXISTS simplefin_connection"))
            session.execute(text("DROP TABLE IF EXISTS simplefin_account_mappings"))
            session.commit()
        finally:
            session.close()
    except Exception:
        pass


def get_simplefin_mappings() -> dict:
    """Get all SimpleFIN account -> local account mappings.
    Returns dict: {simplefin_account_id: {bank_name, account_name, account_type, sfin_name, sfin_org}}
    """
    try:
        from models.database import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='simplefin_account_mappings'"
            )).fetchone()
            if not result:
                return {}
            rows = session.execute(text(
                "SELECT simplefin_account_id, simplefin_account_name, simplefin_org_name, "
                "local_bank_name, local_account_name, local_account_type "
                "FROM simplefin_account_mappings"
            )).fetchall()
            return {
                r[0]: {
                    'sfin_name': r[1],
                    'sfin_org': r[2],
                    'bank_name': r[3],
                    'account_name': r[4],
                    'account_type': r[5],
                }
                for r in rows
            }
        finally:
            session.close()
    except Exception:
        return {}


def save_simplefin_mapping(simplefin_account_id: str, simplefin_account_name: str,
                           simplefin_org_name: str, local_bank_name: str,
                           local_account_name: str, local_account_type: str):
    """Save or update a SimpleFIN account mapping."""
    from models.database import get_session
    from sqlalchemy import text
    session = get_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS simplefin_account_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                simplefin_account_id TEXT UNIQUE NOT NULL,
                simplefin_account_name TEXT NOT NULL,
                simplefin_org_name TEXT NOT NULL,
                local_bank_name TEXT NOT NULL,
                local_account_name TEXT NOT NULL,
                local_account_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        session.execute(text("""
            INSERT INTO simplefin_account_mappings
                (simplefin_account_id, simplefin_account_name, simplefin_org_name,
                 local_bank_name, local_account_name, local_account_type, created_at)
            VALUES (:sid, :sname, :sorg, :lbank, :lacct, :ltype, :ts)
            ON CONFLICT(simplefin_account_id) DO UPDATE SET
                simplefin_account_name=:sname, simplefin_org_name=:sorg,
                local_bank_name=:lbank, local_account_name=:lacct, local_account_type=:ltype
        """), {
            "sid": simplefin_account_id, "sname": simplefin_account_name,
            "sorg": simplefin_org_name, "lbank": local_bank_name,
            "lacct": local_account_name, "ltype": local_account_type,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        session.commit()
    finally:
        session.close()


def remove_simplefin_mapping(simplefin_account_id: str):
    """Remove a SimpleFIN account mapping."""
    try:
        from models.database import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            session.execute(text(
                "DELETE FROM simplefin_account_mappings WHERE simplefin_account_id = :sid"
            ), {"sid": simplefin_account_id})
            session.commit()
        finally:
            session.close()
    except Exception:
        pass

