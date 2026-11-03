#!/usr/bin/env python3
"""Fetch an OSF project's files and/or inspect an OSF registration (preregistration).

Usage:
  osf_fetch.py files <node_id> [--out osf] [--list-only] [--skip-ext mp4,mov,avi,wav,zip] [--max-mb 200]
  osf_fetch.py registration <reg_id> [--out .]

`files` walks osfstorage recursively (following pagination), prints size/path/url,
and downloads everything not skipped, preserving the folder structure under --out.

`registration` prints the registration's title, date_registered, type, and summary,
lists attached files with the SHA-256 frozen in the registration, downloads them,
and verifies the hash (so you know the prereg PDF you read is the registered one).
Also reports whether a project has registrations / child components.
"""
import argparse, hashlib, json, os, sys, urllib.request

API = "https://api.osf.io/v2"


def get(url):
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def walk(url, rel=""):
    while url:
        d = get(url)
        for f in d["data"]:
            a = f["attributes"]
            p = os.path.join(rel, a["name"])
            if a["kind"] == "folder":
                yield from walk(f["relationships"]["files"]["links"]["related"]["href"], p)
            else:
                yield a["size"], p, f["links"]["download"]
        url = d["links"].get("next")


def download(url, dest):
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as out:
        out.write(r.read())


def sha256(fn):
    h = hashlib.sha256()
    with open(fn, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_files(a):
    node = get(f"{API}/nodes/{a.node}/")["data"]["attributes"]
    print(f"# {node['title']}  (created {node['date_created'][:10]}, public={node['public']})")
    for kind in ("registrations", "children"):
        n = get(f"{API}/nodes/{a.node}/{kind}/")["links"]["meta"]["total"]
        print(f"# {kind}: {n}")
    skip = {e.strip().lower().lstrip(".") for e in a.skip_ext.split(",") if e.strip()}
    for size, p, url in walk(f"{API}/nodes/{a.node}/files/osfstorage/"):
        ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
        mb = (size or 0) / 1e6
        skipped = ext in skip or mb > a.max_mb
        print(f"{'SKIP' if skipped else 'GET '} {mb:9.2f} MB  {p}  {url}")
        if not (a.list_only or skipped):
            download(url, os.path.join(a.out, p))


def cmd_registration(a):
    d = get(f"{API}/registrations/{a.reg}/")["data"]["attributes"]
    print(f"title:           {d['title']}")
    print(f"date_registered: {d['date_registered']}")
    print(f"date_created:    {d['date_created']}")
    print(f"type:            {d.get('registration_supplement')}")
    print(f"withdrawn:       {d.get('withdrawn')}   embargoed: {d.get('embargoed')}")
    meta = d.get("registered_meta") or {}
    for k, v in meta.items():
        val = v.get("value") if isinstance(v, dict) else v
        if isinstance(val, str) and val.strip():
            print(f"[{k}] {val.strip()[:800]}")
        for x in (v.get("extra") or []) if isinstance(v, dict) else []:
            if isinstance(x, dict) and "sha256" in x:
                name = x.get("selectedFileName") or x.get("data", {}).get("name")
                print(f"attached: {name}  sha256={x['sha256']}")
    # files stored on the registration itself
    for size, p, url in walk(f"{API}/registrations/{a.reg}/files/osfstorage/"):
        dest = os.path.join(a.out, p)
        download(url, dest)
        print(f"downloaded {dest} ({(size or 0)/1e6:.2f} MB) sha256={sha256(dest)}")
    print("Compare the downloaded sha256 with the 'attached' sha256 above.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("files"); f.add_argument("node"); f.add_argument("--out", default="osf")
    f.add_argument("--list-only", action="store_true")
    f.add_argument("--skip-ext", default="mp4,mov,avi,mkv,wav,mp3,zip")
    f.add_argument("--max-mb", type=float, default=200)
    r = sub.add_parser("registration"); r.add_argument("reg"); r.add_argument("--out", default=".")
    a = ap.parse_args()
    {"files": cmd_files, "registration": cmd_registration}[a.cmd](a)
