#!/usr/bin/env python3
"""
SQL Gen Onboarding API Client

Unified CLI for all SQL Generation onboarding API operations.
Used by the sql-gen-onboarding Copilot skill to invoke APIs and poll for status.

Usage:
    python3 sqlgen_api.py <command> [options]

Commands:
    health                 Health check
    create-vectorstore     Create DB session, VectorStore, and disconnect
    upload-table-desc      Upload table descriptions
    upload-column-desc     Upload column descriptions
    upload-acronyms        Upload acronyms
    upload-files           Upload metadata files (synonyms, taxonomy, autotaxonomy)
    upload-user-profiles   Upload user profiles
    run-index-scripts      Run mandatory index scripts (with optional --wait)
    run-autotaxonomy       Run AutoTaxonomy script (with optional --wait --download)
    get-status             Get SQL Gen script status
    initialize             Initialize SQL Gen platform (with optional --wait)
    get-vs-status          Get VectorStore status
"""

import argparse
import base64
import json
import os
import sys
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _auth_headers(username: str, password: str) -> dict:
    cred = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {cred}", "accept": "application/json"}


def _print_result(label: str, response: requests.Response):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  Status: {response.status_code}")
    print(f"{'='*60}")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
    print()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_health(args):
    url = args.base_url.rstrip('/') + '/health'
    r = requests.get(url, verify=False, timeout=30)
    _print_result("Health Check", r)
    return r.status_code == 200


def cmd_create_vectorstore(args):
    base = args.base_url.rstrip('/')
    headers = _auth_headers(args.username, args.password)

    # 1. Create session
    print("Creating DB session...")
    session_url = base + '/session'
    r = requests.post(session_url, headers=headers,
                      json={'database_name': args.database}, verify=False, timeout=60)
    _print_result("Create Session", r)
    if r.status_code not in (200, 201):
        print("ERROR: Failed to create session")
        return False
    session_id = r.cookies.get("session_id")
    cookies = {'session_id': session_id}

    # 2. Create naming patterns if provided
    if args.include_patterns:
        for pattern in args.include_patterns.split(','):
            pattern = pattern.strip()
            if pattern:
                print(f"Creating pattern: {pattern}")
                pat_url = f"{base}/patterns/{pattern}?pattern_string={pattern}&log_level=1"
                r = requests.post(pat_url, headers=headers, cookies=cookies, verify=False, timeout=30)
                _print_result(f"Create Pattern: {pattern}", r)

    # 3. Create VectorStore
    print(f"Creating VectorStore: {args.vs_name}")
    vs_url = f"{base}/vectorstores/{args.vs_name}?log_level=1"
    vs_params = {
        'embeddings_model': args.embeddings_model,
        'search_algorithm': 'VECTORDISTANCE',
        'top_k': 10,
    }
    vs_index = {'target_database': args.database}
    if args.include_patterns:
        vs_index['include_patterns'] = [p.strip() for p in args.include_patterns.split(',')]
    data = {
        'vs_parameters': json.dumps(vs_params),
        'vs_index': json.dumps(vs_index),
    }
    r = requests.post(vs_url, headers=headers, data=data, cookies=cookies, verify=False, timeout=120)
    _print_result("Create VectorStore", r)

    # 4. Poll for READY status
    print("Waiting for VectorStore to be READY...")
    vs_ready = False
    vs_failed = False
    for attempt in range(120):
        time.sleep(10)
        r = requests.get(vs_url, headers=headers, cookies=cookies, verify=False, timeout=30)
        try:
            body = r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text
        except Exception:
            body = r.text
        status_text = str(body)
        print(f"  Poll {attempt+1}: {status_text[:200]}")
        if 'READY' in status_text.upper():
            print("VectorStore is READY.")
            vs_ready = True
            break
        if 'FAILED' in status_text.upper() or 'ERROR' in status_text.upper():
            print("ERROR: VectorStore creation failed.")
            vs_failed = True
            break
    else:
        print("WARNING: Timed out waiting for VectorStore READY status.")

    # 5. Disconnect session
    print("Disconnecting session...")
    r = requests.delete(session_url, headers=headers, cookies=cookies, verify=False, timeout=30)
    _print_result("Disconnect Session", r)
    if vs_ready:
        return True
    if vs_failed:
        return False
    return False


def cmd_upload_table_desc(args):
    url = f"{args.base_url.rstrip('/')}/table-descriptions"
    headers = _auth_headers(args.username, args.password)
    headers.pop("accept", None)  # multipart
    params = {"hostname": args.hostname, "database": args.database, "replace_existing": True}
    with open(args.file, 'rb') as f:
        files = {"table_description_file": (os.path.basename(args.file), f)}
        r = requests.post(url, params=params, files=files,
                          auth=(args.username, args.password),
                          headers={"accept": "application/json"}, verify=False, timeout=120)
    _print_result("Upload Table Descriptions", r)
    return r.status_code in (200, 201)


def cmd_upload_column_desc(args):
    url = f"{args.base_url.rstrip('/')}/column-descriptions"
    params = {"hostname": args.hostname, "database": args.database, "replace_existing": True}
    with open(args.file, 'rb') as f:
        files = {"column_description_file": (os.path.basename(args.file), f)}
        r = requests.post(url, params=params, files=files,
                          auth=(args.username, args.password),
                          headers={"accept": "application/json"}, verify=False, timeout=120)
    _print_result("Upload Column Descriptions", r)
    return r.status_code in (200, 201)


def cmd_upload_acronyms(args):
    url = f"{args.base_url.rstrip('/')}/acronyms"
    params = {"hostname": args.hostname, "database": args.database, "replace_existing": True}
    with open(args.file, 'rb') as f:
        files = {"acronyms_file": (os.path.basename(args.file), f)}
        r = requests.post(url, params=params, files=files,
                          auth=(args.username, args.password),
                          headers={"accept": "application/json"}, verify=False, timeout=120)
    _print_result("Upload Acronyms", r)
    return r.status_code in (200, 201)


def cmd_upload_files(args):
    url = f"{args.base_url.rstrip('/')}/files"
    params = {
        "hostname": args.hostname, "database": args.database,
        "vectorstore": args.vs_name, "replace_existing": True,
    }
    files = {}
    if args.synonyms and os.path.exists(args.synonyms):
        files["synonyms_file"] = (os.path.basename(args.synonyms), open(args.synonyms, 'rb'))
    if args.taxonomy_disambiguation and os.path.exists(args.taxonomy_disambiguation):
        files["taxonomy_disambiguation_file"] = (os.path.basename(args.taxonomy_disambiguation),
                                                  open(args.taxonomy_disambiguation, 'rb'))
    if args.autotaxonomy and os.path.exists(args.autotaxonomy):
        files["autotaxonomy_file"] = (os.path.basename(args.autotaxonomy), open(args.autotaxonomy, 'rb'))

    if not files:
        print("ERROR: No valid files specified.")
        return False

    r = requests.post(url, params=params, files=files,
                      auth=(args.username, args.password),
                      headers={"accept": "application/json"}, verify=False, timeout=120)
    _print_result("Upload Metadata Files", r)
    for v in files.values():
        v[1].close()
    return r.status_code in (200, 201)


def cmd_upload_user_profiles(args):
    url = f"{args.base_url.rstrip('/')}/user-profiles"
    params = {
        "hostname": args.hostname, "database": args.database,
        "vectorstore": args.vs_name, "replace_existing": True,
    }
    with open(args.file, 'rb') as f:
        files = {"user_profiles_file": (os.path.basename(args.file), f)}
        r = requests.post(url, params=params, files=files,
                          auth=(args.username, args.password),
                          headers={"accept": "application/json"}, verify=False, timeout=120)
    _print_result("Upload User Profiles", r)
    return r.status_code in (200, 201)


def _poll_status(args, target_scripts, label="scripts"):
    """Poll SQL Gen status until all target scripts reach SUCCEEDED or FAILED."""
    url = f"{args.base_url.rstrip('/')}/status"
    params = {"hostname": args.hostname, "database": args.database, "vectorstore": args.vs_name}
    target_set = {s.lower() for s in target_scripts}

    for attempt in range(180):  # up to 30 min at 10s intervals
        time.sleep(10)
        r = requests.get(url, params=params,
                         auth=(args.username, args.password),
                         headers={"accept": "application/json"}, verify=False, timeout=30)
        try:
            body = r.json()
        except Exception:
            print(f"  Poll {attempt+1}: {r.text[:200]}")
            continue

        statuses = {}
        for item in body.get('data', []):
            script = item.get('script', '').lower()
            if script in target_set:
                statuses[script] = item.get('status', 'UNKNOWN')

        status_str = ', '.join(f"{k}: {v}" for k, v in statuses.items())
        print(f"  Poll {attempt+1}: {status_str}")

        all_done = all(
            statuses.get(s, 'UNKNOWN') in ('SUCCEEDED', 'FAILED')
            for s in target_set
        )
        if all_done:
            failed = [s for s in target_set if statuses.get(s) == 'FAILED']
            if failed:
                print(f"ERROR: {label} failed: {', '.join(failed)}")
                return False
            print(f"All {label} SUCCEEDED.")
            return True

    print(f"WARNING: Timed out waiting for {label}.")
    return False


def cmd_run_index_scripts(args):
    url = f"{args.base_url.rstrip('/')}/indexing-scripts"
    params = {"hostname": args.hostname, "database": args.database, "vectorstore": args.vs_name}
    r = requests.post(url, params=params,
                      auth=(args.username, args.password),
                      headers={"accept": "application/json"}, verify=False, timeout=60)
    _print_result("Run Index Scripts", r)
    if r.status_code != 200:
        return False
    if args.wait:
        return _poll_status(args, ['featureindex', 'featureindexdescription', 'indexcolumnuniqueness'],
                           "index scripts")
    return True


def cmd_run_autotaxonomy(args):
    url = f"{args.base_url.rstrip('/')}/autotaxonomy-script"
    params = {
        "hostname": args.hostname, "database": args.database,
        "vectorstore": args.vs_name, "table_pattern": args.table_pattern,
    }
    r = requests.post(url, params=params,
                      auth=(args.username, args.password),
                      headers={"accept": "application/json"}, verify=False, timeout=60)
    _print_result("Run AutoTaxonomy", r)
    if r.status_code != 200:
        return False
    if args.wait:
        ok = _poll_status(args, ['autotaxonomy'], "AutoTaxonomy")
        if ok and args.download:
            # Download the generated file
            dl_url = f"{args.base_url.rstrip('/')}/autotaxonomy-file"
            dl_params = {"hostname": args.hostname, "database": args.database, "vectorstore": args.vs_name}
            r = requests.get(dl_url, params=dl_params,
                             auth=(args.username, args.password),
                             headers={"accept": "application/json"}, verify=False, timeout=60)
            if r.status_code == 200:
                with open(args.download, 'wb') as f:
                    f.write(r.content)
                print(f"AutoTaxonomy file downloaded to: {args.download}")
            else:
                _print_result("Download AutoTaxonomy", r)
        return ok
    return True


def cmd_get_status(args):
    url = f"{args.base_url.rstrip('/')}/status"
    params = {"hostname": args.hostname, "database": args.database, "vectorstore": args.vs_name}
    r = requests.get(url, params=params,
                     auth=(args.username, args.password),
                     headers={"accept": "application/json"}, verify=False, timeout=30)
    _print_result("SQL Gen Status", r)
    return r.status_code == 200


def cmd_initialize(args):
    if args.wait and not args.vs_name:
        print("ERROR: --vs-name is required when using --wait for initialize.")
        return False

    url = f"{args.base_url.rstrip('/')}/sql-gen-initialization"
    params = {"hostname": args.hostname, "database": args.database}
    r = requests.post(url, params=params,
                      auth=(args.username, args.password),
                      headers={"accept": "application/json"}, verify=False, timeout=60)
    _print_result("Initialize SQL Gen", r)
    if r.status_code != 200:
        return False
    if args.wait:
        return _poll_status(args, ['initializesqlgen'], "SQL Gen Initialization")
    return True


def cmd_list_table_desc(args):
    url = f"{args.base_url.rstrip('/')}/table-descriptions"
    params = {"hostname": args.hostname, "database": args.database}
    r = requests.get(url, params=params,
                     auth=(args.username, args.password),
                     headers={"accept": "application/json"}, verify=False, timeout=30)
    _print_result("List Table Descriptions", r)
    return r.status_code == 200


def cmd_list_column_desc(args):
    url = f"{args.base_url.rstrip('/')}/column-descriptions"
    params = {"hostname": args.hostname, "database": args.database}
    r = requests.get(url, params=params,
                     auth=(args.username, args.password),
                     headers={"accept": "application/json"}, verify=False, timeout=30)
    _print_result("List Column Descriptions", r)
    return r.status_code == 200


def cmd_generate_desc(args):
    """Generate starter table and column description CSV files from MCP metadata JSON.

    Expects --mcp-json to point to a JSON file containing MCP columnDescription
    results keyed by table name, e.g.:
      {"Complaints": [{"ColumnName": "...", "Type": "...", ...}, ...], ...}

    Outputs two CSV files:
      <output-dir>/table_descriptions.csv
      <output-dir>/column_descriptions.csv
    """
    import csv

    with open(args.mcp_json, 'r') as f:
        mcp_data = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    table_csv = os.path.join(args.output_dir, 'table_descriptions.csv')
    col_csv = os.path.join(args.output_dir, 'column_descriptions.csv')

    with open(table_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['database_name', 'table_name', 'table_comment'])
        for table_name in sorted(mcp_data.keys()):
            w.writerow([args.database, table_name, ''])

    with open(col_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['database_name', 'table_name', 'column_name', 'column_comment'])
        for table_name in sorted(mcp_data.keys()):
            for col in mcp_data[table_name]:
                col_name = col.get('ColumnName', col.get('columnName', ''))
                w.writerow([args.database, table_name, col_name, ''])

    print(f"Generated: {table_csv} ({len(mcp_data)} tables)")
    total_cols = sum(len(cols) for cols in mcp_data.values())
    print(f"Generated: {col_csv} ({total_cols} columns)")
    return True


def cmd_get_vs_status(args):
    base = args.base_url.rstrip('/')
    headers = _auth_headers(args.username, args.password)
    # Need a session for VS endpoints
    session_url = base + '/session'
    r = requests.post(session_url, headers=headers,
                      json={'database_name': args.database}, verify=False, timeout=60)
    if r.status_code not in (200, 201):
        _print_result("Create Session (for VS status)", r)
        return False
    session_id = r.cookies.get("session_id")
    cookies = {'session_id': session_id}

    vs_url = f"{base}/vectorstores/{args.vs_name}?log_level=1"
    r = requests.get(vs_url, headers=headers, cookies=cookies, verify=False, timeout=30)
    _print_result("VectorStore Status", r)

    requests.delete(session_url, headers=headers, cookies=cookies, verify=False, timeout=30)
    return r.status_code == 200


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SQL Gen Onboarding API Client")
    sub = parser.add_subparsers(dest='command', required=True)

    # Common args
    def add_common(p, need_hostname=True, need_vs=False):
        p.add_argument('--base-url', required=True, help='SQL Gen API base URL')
        if need_hostname:
            p.add_argument('--hostname', required=True, help='Database host IP')
            p.add_argument('--database', required=True, help='Database name')
            p.add_argument('--username', required=True, help='Admin username')
            p.add_argument('--password', required=True, help='Admin password')
        if need_vs:
            p.add_argument('--vs-name', required=True, help='VectorStore name')

    # health
    p = sub.add_parser('health')
    p.add_argument('--base-url', required=True)

    # create-vectorstore
    p = sub.add_parser('create-vectorstore')
    add_common(p, need_vs=True)
    p.add_argument('--embeddings-model', default='amazon.titan-embed-text-v2:0')
    p.add_argument('--include-patterns', default=None, help='Comma-separated patterns')

    # upload-table-desc
    p = sub.add_parser('upload-table-desc')
    add_common(p)
    p.add_argument('--file', required=True, help='Path to table descriptions file')

    # upload-column-desc
    p = sub.add_parser('upload-column-desc')
    add_common(p)
    p.add_argument('--file', required=True, help='Path to column descriptions file')

    # upload-acronyms
    p = sub.add_parser('upload-acronyms')
    add_common(p)
    p.add_argument('--file', required=True, help='Path to acronyms file')

    # upload-files
    p = sub.add_parser('upload-files')
    add_common(p, need_vs=True)
    p.add_argument('--synonyms', default=None)
    p.add_argument('--taxonomy-disambiguation', default=None)
    p.add_argument('--autotaxonomy', default=None)

    # upload-user-profiles
    p = sub.add_parser('upload-user-profiles')
    add_common(p, need_vs=True)
    p.add_argument('--file', required=True, help='Path to user profiles file')

    # run-index-scripts
    p = sub.add_parser('run-index-scripts')
    add_common(p, need_vs=True)
    p.add_argument('--wait', action='store_true', help='Poll until complete')

    # run-autotaxonomy
    p = sub.add_parser('run-autotaxonomy')
    add_common(p, need_vs=True)
    p.add_argument('--table-pattern', required=True, help='Table naming pattern')
    p.add_argument('--wait', action='store_true', help='Poll until complete')
    p.add_argument('--download', default=None, help='Download path for generated file')

    # get-status
    p = sub.add_parser('get-status')
    add_common(p, need_vs=True)

    # initialize
    p = sub.add_parser('initialize')
    add_common(p)
    p.add_argument('--wait', action='store_true', help='Poll until complete')
    # initialize needs vs_name for status polling
    p.add_argument('--vs-name', default=None, help='VectorStore name (for status polling)')

    # list-table-desc
    p = sub.add_parser('list-table-desc')
    add_common(p)

    # list-column-desc
    p = sub.add_parser('list-column-desc')
    add_common(p)

    # generate-desc
    p = sub.add_parser('generate-desc')
    p.add_argument('--database', required=True, help='Database name')
    p.add_argument('--mcp-json', required=True, help='Path to MCP column metadata JSON')
    p.add_argument('--output-dir', required=True, help='Output directory for CSV files')

    # get-vs-status
    p = sub.add_parser('get-vs-status')
    add_common(p, need_vs=True)

    args = parser.parse_args()

    commands = {
        'health': cmd_health,
        'create-vectorstore': cmd_create_vectorstore,
        'upload-table-desc': cmd_upload_table_desc,
        'upload-column-desc': cmd_upload_column_desc,
        'upload-acronyms': cmd_upload_acronyms,
        'upload-files': cmd_upload_files,
        'upload-user-profiles': cmd_upload_user_profiles,
        'run-index-scripts': cmd_run_index_scripts,
        'run-autotaxonomy': cmd_run_autotaxonomy,
        'get-status': cmd_get_status,
        'initialize': cmd_initialize,
        'get-vs-status': cmd_get_vs_status,
        'list-table-desc': cmd_list_table_desc,
        'list-column-desc': cmd_list_column_desc,
        'generate-desc': cmd_generate_desc,
    }

    ok = commands[args.command](args)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
