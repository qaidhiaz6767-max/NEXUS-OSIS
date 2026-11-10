# Private backups and controlled restoration

`nexus.backup` is a working administrative CLI for an initialized schema 1 or 2
workspace database. It is not exposed to the model or HTTP frontend. No automatic
backup job, off-device replication or recovery of a lost passphrase is provided.

Install the optional reviewed cryptography dependency in your local virtual
environment before using it:

```bash
python3 -m pip install -r requirements-security.txt
```

The ordinary offline app still needs only Python's standard library. Development
tests for backups require this dependency. No homemade encryption fallback exists.

## Create and inspect

These commands are examples for an existing initialized OSIS database; they
read the database and create a new private archive. Choose an unused filename
outside the repository. Keep a copy on appropriate private off-device storage
if protection against disk loss is needed; this CLI does not upload it.

```bash
python3 -m nexus.backup create --workspace osis --db data/nexus.sqlite3 --file "$HOME/NEXUS-Backups/osis-before-upgrade.nxbak"
python3 -m nexus.backup inspect --workspace osis --file "$HOME/NEXUS-Backups/osis-before-upgrade.nxbak"
```

Passphrases are requested interactively, never in arguments or chat. Create asks
twice and requires at least 12 characters. Use a strong unique passphrase and keep
it separately. The program refuses overwrite and backup output inside a Git
repository. New archive files use POSIX mode 0600 and newly created directories
0700. Existing directory permissions are not repaired.

Snapshots use SQLite's backup API, not a raw copy of an open database; committed
WAL data is captured consistently and uncommitted work is excluded. Integrity,
foreign keys, workspace identity and supported schema are checked before use.
The current database size cap is 32 MiB, archive cap 64 MiB. The operation is
manual and whole-workspace; there is no retention rotation or differential copy.

## Restore with explicit review

Stop NEXUS and any other process accessing the target SQLite file. Then:

```bash
python3 -m nexus.backup restore --workspace osis --db data/nexus.sqlite3 --file "$HOME/NEXUS-Backups/osis-before-upgrade.nxbak"
```

The CLI authenticates/decrypts, validates and displays record counts before
asking you to type `RESTORE osis`. Cancelling this prompt does not change the
target. An existing target must belong to the same workspace. Symlink targets
are refused. A running app holds a shared POSIX advisory lease; restore requires
an exclusive lease and refuses while that app is using the database.

Before replacing an existing valid target, restore creates a separate encrypted
rollback archive beside the input archive, using the same passphrase. Keep this
file private. A staged SQLite file on the target filesystem is migrated and
checked before atomic replacement. Pending approvals are invalidated and linked
unfinished plans/commands cancelled, preventing old snapshot tokens from replay.
Completed history is preserved. File and directory are fsynced. The rollback
archive is retained if a later step fails.

## Actual security properties and limits

- AES-256-GCM authenticates/encrypts the SQLite payload. A fresh 16-byte salt and
  12-byte nonce are generated. Scrypt derives a 32-byte key (N=32768,r=8,p=1).
  Fixed version/KDF/cipher parameters are validated. Header metadata is authenticated
  as associated data; workspace and creation time in the header are **visible**.
- Wrong passphrase, ciphertext tampering, unsupported schema, foreign workspace,
  invalid SQLite or relationships fail before target replacement. Encryption is
  verified by synthetic round-trip/tampering tests, not an independent audit.
- Live SQLite, chat and plaintext JSON exports are **not encrypted**. Snapshot
  preparation and restore create temporary plaintext files in owner-only locations;
  deletion is not secure erasure. Host account/disk protection remains essential.
- The lease is cooperative. Direct SQLite clients or custom Store instances not
  using runtime leases can bypass it. Stop all database clients before restoring.
  This is a POSIX implementation tested on Linux; macOS behavior is not verified,
  Windows is unsupported for the restore lease.
- No recovery from missing passphrases, automatic cloud backup, disaster-recovery
  service, secure deletion or protection against a compromised local account is
  claimed. Only restore archives you trust; authenticated input does not make a
  deliberately crafted database from an untrusted party safe.

`GET /api/backup` remains a **plaintext business-record JSON export** for
compatibility. It now includes project/task sidecars and meeting relationships,
but excludes chat/pending/command history and has no restore endpoint. Use the
encrypted SQLite CLI for full recovery. Automated recovery drills use temporary
synthetic databases only; no real user backup was read or uploaded in development.
