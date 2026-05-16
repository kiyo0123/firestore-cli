#!/usr/bin/env python3
"""fs — a gcloud-style CLI for learning Google Cloud Firestore.

Tool-agnostic: this is a plain Python CLI. Run it directly with
`python3 fs.py <args>` from any environment (Claude Code, Codex, a shell).

Single external dependency: google-cloud-firestore.
"""

import argparse
import json
import os
import sys

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "firestore-cli",
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_DATABASE = "(default)"

WHERE_OPS = {"==", "!=", "<", "<=", ">", ">=", "in", "array-contains"}


class CliError(Exception):
    """A user-facing error with a friendly message (no traceback)."""


# --------------------------------------------------------------------------- #
# Dependency / client helpers
# --------------------------------------------------------------------------- #

def _require_firestore():
    try:
        from google.cloud import firestore  # noqa: F401
        return firestore
    except ImportError:
        raise CliError(
            "google-cloud-firestore is not installed.\n"
            "  pip install google-cloud-firestore"
        )


def _require_admin():
    try:
        from google.cloud import firestore_admin_v1
        return firestore_admin_v1
    except ImportError:
        raise CliError(
            "google-cloud-firestore (Admin API) is not installed.\n"
            "  pip install google-cloud-firestore"
        )


def get_client(args):
    firestore = _require_firestore()
    project = resolve_project(args)
    database = resolve_database(args)
    try:
        if database and database != DEFAULT_DATABASE:
            return firestore.Client(project=project, database=database)
        return firestore.Client(project=project)
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def resolve_project(args):
    project = (
        getattr(args, "project", None)
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or load_config().get("project")
    )
    if not project:
        # Fall back to ADC default project (may still be None).
        try:
            import google.auth

            _, project = google.auth.default()
        except Exception:  # noqa: BLE001
            project = None
    if not project:
        raise CliError(
            "No GCP project configured. Set one of the following:\n"
            "  fs config set project <PROJECT_ID>\n"
            "  or --project <PROJECT_ID>\n"
            "  or the GOOGLE_CLOUD_PROJECT environment variable"
        )
    return project


def resolve_database(args):
    return (
        getattr(args, "database", None)
        or os.environ.get("FIRESTORE_DATABASE")
        or load_config().get("database")
        or DEFAULT_DATABASE
    )


# --------------------------------------------------------------------------- #
# Path resolution (subcollection-aware)
# --------------------------------------------------------------------------- #

def _segments(path):
    parts = [p for p in path.strip("/").split("/") if p != ""]
    if not parts:
        raise CliError("Path is empty. e.g. users  or  users/alice/orders")
    return parts


def resolve_collection(client, path):
    """Resolve a path to a CollectionReference (odd number of segments)."""
    parts = _segments(path)
    if len(parts) % 2 == 0:
        raise CliError(
            f"'{path}' is a document path. Provide a collection path "
            "(odd number of segments, e.g. users, users/alice/orders)."
        )
    ref = client.collection(parts[0])
    for i in range(1, len(parts), 2):
        ref = ref.document(parts[i]).collection(parts[i + 1])
    return ref


def resolve_document(client, path):
    """Resolve a path to a DocumentReference (even number of segments)."""
    parts = _segments(path)
    if len(parts) % 2 == 1:
        raise CliError(
            f"'{path}' is a collection path. Provide a document path "
            "(even number of segments, e.g. users/alice, users/alice/orders/o1)."
        )
    ref = client.collection(parts[0]).document(parts[1])
    for i in range(2, len(parts), 2):
        ref = ref.collection(parts[i]).document(parts[i + 1])
    return ref


# --------------------------------------------------------------------------- #
# Data input / output
# --------------------------------------------------------------------------- #

def read_data(args):
    raw = None
    if getattr(args, "data_file", None):
        with open(args.data_file, encoding="utf-8") as fh:
            raw = fh.read()
    elif getattr(args, "data", None) is not None:
        if args.data == "@-":
            raw = sys.stdin.read()
        else:
            raw = args.data
    if raw is None:
        raise CliError(
            "No data provided. Use one of --data '<json>' / "
            "--data-file <path> / --data @- (stdin)."
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"--data is not valid JSON: {exc}")
    if not isinstance(value, dict):
        raise CliError("--data must be an object ({...}).")
    return value


def _print_doc(doc_id, data, as_json):
    if as_json:
        print(json.dumps({"id": doc_id, "data": data}, ensure_ascii=False,
                          indent=2, default=str))
        return
    print(f"# {doc_id}")
    if not data:
        print("  (no fields)")
        return
    for key in sorted(data):
        print(f"  {key}: {json.dumps(data[key], ensure_ascii=False, default=str)}")


def _print_table(rows):
    if not rows:
        print("(0 items)")
        return
    cols = ["ID"] + sorted({k for _, d in rows for k in (d or {})})
    widths = {c: len(c) for c in cols}
    table = []
    for doc_id, data in rows:
        cells = {"ID": doc_id}
        for c in cols[1:]:
            v = (data or {}).get(c, "")
            cells[c] = json.dumps(v, ensure_ascii=False, default=str) if v != "" else ""
        for c in cols:
            widths[c] = max(widths[c], len(cells[c]))
        table.append(cells)
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    print(line)
    print("  ".join("-" * widths[c] for c in cols))
    for cells in table:
        print("  ".join(cells[c].ljust(widths[c]) for c in cols))
    print(f"\n{len(rows)} items")


def _friendly(exc):
    """Convert common Google API exceptions into CliError with hints."""
    name = type(exc).__name__
    msg = str(exc)
    if name in ("DefaultCredentialsError",) or "default credentials" in msg.lower():
        return CliError(
            "No GCP credentials found. Set one of the following:\n"
            "  gcloud auth application-default login\n"
            "  or the GOOGLE_APPLICATION_CREDENTIALS=<service-account.json> "
            "environment variable"
        )
    if name == "NotFound" or "404" in msg:
        return CliError(f"Not found (NotFound): {msg}")
    if name == "PermissionDenied" or "403" in msg:
        return CliError(
            f"Permission denied (PermissionDenied): {msg}\n"
            "Check your IAM roles (e.g. roles/datastore.user)."
        )
    if name == "AlreadyExists" or "409" in msg:
        return CliError(f"Already exists (AlreadyExists): {msg}")
    return CliError(f"{name}: {msg}")


# --------------------------------------------------------------------------- #
# Commands: config
# --------------------------------------------------------------------------- #

def cmd_config_set(args):
    cfg = load_config()
    cfg[args.key] = args.value
    save_config(cfg)
    print(f"Set: {args.key} = {args.value}")
    print(f"(saved to: {CONFIG_PATH})")


def cmd_config_list(args):
    cfg = load_config()
    print(f"# config ({CONFIG_PATH})")
    if not cfg:
        print("  (not configured)")
    for k in sorted(cfg):
        print(f"  {k}: {cfg[k]}")
    print("# effective values")
    print(f"  project:  {os.environ.get('GOOGLE_CLOUD_PROJECT') or cfg.get('project') or '(ADC default / not set)'}")
    print(f"  database: {os.environ.get('FIRESTORE_DATABASE') or cfg.get('database') or DEFAULT_DATABASE}")


# --------------------------------------------------------------------------- #
# Commands: db (Admin API)
# --------------------------------------------------------------------------- #

def cmd_db_create(args):
    admin = _require_admin()
    project = resolve_project(args)
    database_id = args.database or DEFAULT_DATABASE
    try:
        client = admin.FirestoreAdminClient()
        db = admin.types.Database(
            type_=admin.types.Database.DatabaseType.FIRESTORE_NATIVE,
            location_id=args.location,
        )
        op = client.create_database(
            parent=f"projects/{project}",
            database=db,
            database_id=database_id,
        )
        print(f"Creating... (database_id={database_id}, location={args.location})")
        result = op.result(timeout=300)
        print(f"Created database: {result.name}")
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)


def cmd_db_list(args):
    admin = _require_admin()
    project = resolve_project(args)
    try:
        client = admin.FirestoreAdminClient()
        resp = client.list_databases(parent=f"projects/{project}")
        dbs = list(resp.databases)
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    if not dbs:
        print("(no databases)")
        return
    for d in dbs:
        loc = getattr(d, "location_id", "")
        print(f"  {d.name}  (location={loc})")
    print(f"\n{len(dbs)} items")


def cmd_db_describe(args):
    admin = _require_admin()
    project = resolve_project(args)
    database_id = args.database or DEFAULT_DATABASE
    try:
        client = admin.FirestoreAdminClient()
        d = client.get_database(
            name=f"projects/{project}/databases/{database_id}"
        )
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    print(f"# {d.name}")
    print(f"  location_id: {getattr(d, 'location_id', '')}")
    print(f"  type: {getattr(d, 'type_', '')}")
    print(f"  concurrency_mode: {getattr(d, 'concurrency_mode', '')}")


# --------------------------------------------------------------------------- #
# Commands: collections
# --------------------------------------------------------------------------- #

def cmd_collections_list(args):
    client = get_client(args)
    try:
        if args.doc_path:
            cols = resolve_document(client, args.doc_path).collections()
        else:
            cols = client.collections()
        ids = [c.id for c in cols]
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    scope = args.doc_path or "(root)"
    print(f"# collections under {scope}")
    if not ids:
        print("  (none)")
        return
    for cid in ids:
        print(f"  {cid}")
    print(f"\n{len(ids)} items")


def cmd_collections_create(args):
    client = get_client(args)
    data = read_data(args)
    try:
        col = resolve_collection(client, args.collection)
        col.document(args.doc_id).set(data)
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    print(f"Created {args.collection}/{args.doc_id}")
    print("(In Firestore, a collection is created implicitly when its first document is written)")


# --------------------------------------------------------------------------- #
# Commands: documents
# --------------------------------------------------------------------------- #

def cmd_documents_list(args):
    client = get_client(args)
    try:
        col = resolve_collection(client, args.collection)
        query = col.limit(args.limit) if args.limit else col
        rows = [(d.id, d.to_dict()) for d in query.stream()]
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    _print_table(rows)


def cmd_documents_get(args):
    client = get_client(args)
    try:
        snap = resolve_document(client, args.doc_path).get()
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    if not snap.exists:
        raise CliError(f"Document does not exist: {args.doc_path}")
    _print_doc(snap.id, snap.to_dict(), args.format == "json")


def cmd_documents_add(args):
    client = get_client(args)
    data = read_data(args)
    try:
        col = resolve_collection(client, args.collection)
        _, ref = col.add(data)
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    print(f"Created {args.collection}/{ref.id}")


def cmd_documents_set(args):
    client = get_client(args)
    data = read_data(args)
    try:
        ref = resolve_document(client, args.doc_path)
        ref.set(data, merge=args.merge)
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    verb = "Merged" if args.merge else "Set"
    print(f"{verb} {args.doc_path}")


def cmd_documents_update(args):
    client = get_client(args)
    data = read_data(args)
    try:
        ref = resolve_document(client, args.doc_path)
        ref.update(data)
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    print(f"Updated {args.doc_path}")


def cmd_documents_delete(args):
    client = get_client(args)
    if not args.yes:
        if not sys.stdin.isatty():
            raise CliError(
                f"About to delete '{args.doc_path}'. --yes is required in "
                "non-interactive mode."
            )
        ans = input(f"Delete '{args.doc_path}'? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Aborted.")
            return
    try:
        resolve_document(client, args.doc_path).delete()
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    print(f"Deleted {args.doc_path}")


# --------------------------------------------------------------------------- #
# Commands: query
# --------------------------------------------------------------------------- #

def _parse_where(expr):
    tokens = expr.split(None, 2)
    if len(tokens) != 3:
        raise CliError(
            f"Invalid --where '{expr}'. Use the form 'field OP value'."
            f" e.g. --where \"age >= 18\""
        )
    field, op, raw_value = tokens
    if op not in WHERE_OPS:
        raise CliError(
            f"Unsupported operator '{op}'. Supported: {', '.join(sorted(WHERE_OPS))}"
        )
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value  # treat as plain string
    return field, op, value


def cmd_query(args):
    client = get_client(args)
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
    except ImportError:
        FieldFilter = None
    try:
        q = resolve_collection(client, args.collection)
        for expr in args.where or []:
            field, op, value = _parse_where(expr)
            if FieldFilter is not None:
                q = q.where(filter=FieldFilter(field, op, value))
            else:
                q = q.where(field, op, value)
        if args.order_by:
            field = args.order_by
            direction = "ASCENDING"
            if ":" in args.order_by:
                field, _, suffix = args.order_by.partition(":")
                if suffix.lower() in ("desc", "descending"):
                    direction = "DESCENDING"
            q = q.order_by(field, direction=direction)
        if args.limit:
            q = q.limit(args.limit)
        rows = [(d.id, d.to_dict()) for d in q.stream()]
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc)
    if args.format == "json":
        print(json.dumps(
            [{"id": i, "data": d} for i, d in rows],
            ensure_ascii=False, indent=2, default=str,
        ))
    else:
        _print_table(rows)


# --------------------------------------------------------------------------- #
# Argument parser
# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(
        prog="fs",
        description="A gcloud-style CLI for learning Firestore",
    )
    p.add_argument("--project", help="GCP project ID")
    p.add_argument("--database", help=f"Firestore database ID (default: {DEFAULT_DATABASE})")
    sub = p.add_subparsers(dest="noun", required=True)

    # config
    c = sub.add_parser("config", help="Show or change configuration")
    csub = c.add_subparsers(dest="verb", required=True)
    cset = csub.add_parser("set", help="Save a config value (project / database)")
    cset.add_argument("key", choices=["project", "database"])
    cset.add_argument("value")
    cset.set_defaults(func=cmd_config_set)
    clist = csub.add_parser("list", help="Show current config and effective values")
    clist.set_defaults(func=cmd_config_list)

    # db
    d = sub.add_parser("db", help="Database operations (Admin API)")
    dsub = d.add_subparsers(dest="verb", required=True)
    dc = dsub.add_parser("create", help="Create a database")
    dc.add_argument("--database", default=DEFAULT_DATABASE, help="database ID")
    dc.add_argument("--location", default="nam5", help="location (default: nam5)")
    dc.set_defaults(func=cmd_db_create)
    dl = dsub.add_parser("list", help="List databases")
    dl.set_defaults(func=cmd_db_list)
    dd = dsub.add_parser("describe", help="Describe a database")
    dd.add_argument("--database", default=DEFAULT_DATABASE)
    dd.set_defaults(func=cmd_db_describe)

    # collections
    col = sub.add_parser("collections", help="List or create collections")
    colsub = col.add_subparsers(dest="verb", required=True)
    cl = colsub.add_parser("list", help="List collections at root or under a document")
    cl.add_argument("doc_path", nargs="?", help="e.g. users/alice")
    cl.set_defaults(func=cmd_collections_list)
    cc = colsub.add_parser("create", help="Create the first document to materialize a collection")
    cc.add_argument("collection", help="collection path, e.g. users")
    cc.add_argument("--doc-id", required=True, dest="doc_id")
    cc.add_argument("--data")
    cc.add_argument("--data-file", dest="data_file")
    cc.set_defaults(func=cmd_collections_create)

    # documents
    doc = sub.add_parser("documents", help="Document CRUD")
    docsub = doc.add_subparsers(dest="verb", required=True)

    dls = docsub.add_parser("list", help="List documents in a collection")
    dls.add_argument("collection", help="collection path, e.g. users")
    dls.add_argument("--limit", type=int)
    dls.set_defaults(func=cmd_documents_list)

    dg = docsub.add_parser("get", help="Get a document")
    dg.add_argument("doc_path", help="document path, e.g. users/alice")
    dg.add_argument("--format", choices=["text", "json"], default="text")
    dg.set_defaults(func=cmd_documents_get)

    da = docsub.add_parser("add", help="Add a document with an auto-generated ID")
    da.add_argument("collection", help="collection path")
    da.add_argument("--data")
    da.add_argument("--data-file", dest="data_file")
    da.set_defaults(func=cmd_documents_add)

    ds = docsub.add_parser("set", help="Create or overwrite a document")
    ds.add_argument("doc_path")
    ds.add_argument("--data")
    ds.add_argument("--data-file", dest="data_file")
    ds.add_argument("--merge", action="store_true", help="Merge, keeping existing fields")
    ds.set_defaults(func=cmd_documents_set)

    du = docsub.add_parser("update", help="Update fields of an existing document")
    du.add_argument("doc_path")
    du.add_argument("--data")
    du.add_argument("--data-file", dest="data_file")
    du.set_defaults(func=cmd_documents_update)

    dd2 = docsub.add_parser("delete", help="Delete a document")
    dd2.add_argument("doc_path")
    dd2.add_argument("--yes", action="store_true", help="Skip confirmation")
    dd2.set_defaults(func=cmd_documents_delete)

    # query
    q = sub.add_parser("query", help="Query a collection")
    q.add_argument("collection", help="collection path")
    q.add_argument("--where", action="append",
                   help='"field OP value", e.g. "age >= 18" (repeatable)')
    q.add_argument("--order-by", dest="order_by",
                   help="field[:desc], e.g. created:desc")
    q.add_argument("--limit", type=int)
    q.add_argument("--format", choices=["text", "json"], default="text")
    q.set_defaults(func=cmd_query)

    # help
    h = sub.add_parser("help", help="Show usage")
    h.set_defaults(func=lambda a: p.print_help())

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        rc = args.func(args)
        return rc or 0
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
