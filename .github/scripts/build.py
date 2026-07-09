import glob
import os
import re
import shutil
import struct
import subprocess
import sys

try:
    from PIL import Image
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], check=True)
    from PIL import Image

CATALOG = "catalog.bin"
DIST_DIR = "dist"
MAGIC = b"FCAT"
FORMAT_VERSION = 2
HEADER_SIZE = 16
RECORD_SIZE = 36
ICON_DIM = 10
ICON_BYTES = 20

CATEGORIES = [
    "Bluetooth",
    "Games",
    "GPIO",
    "iButton",
    "Infrared",
    "Media",
    "NFC",
    "RFID",
    "Scripts",
    "Sub-GHz",
    "Tools",
    "USB",
    "Settings",
]
CATEGORY_FALLBACK = CATEGORIES.index("Tools")

APPID_RE = re.compile(r"appid\s*=\s*[\"']([^\"']+)[\"']")
NAME_RE = re.compile(r"\bname\s*=\s*[\"']([^\"']+)[\"']")
ICON_RE = re.compile(r"fap_icon\s*=\s*[\"']([^\"']+)[\"']")
CATEGORY_RE = re.compile(r"fap_category\s*=\s*[\"']([^\"']+)[\"']")
FAP_VERSION_RE = re.compile(r"fap_version\s*=\s*([^\n,]+)")


def category_index(name):
    normalized = re.sub(r"[\s_-]", "", name or "").lower()
    for index, category in enumerate(CATEGORIES):
        if re.sub(r"[\s_-]", "", category).lower() == normalized:
            return index
    return CATEGORY_FALLBACK


def read_fam(appdir):
    with open(os.path.join(appdir, "application.fam"), encoding="utf-8", errors="ignore") as f:
        text = f.read()
    appid = APPID_RE.search(text)
    if not appid:
        raise RuntimeError("no appid in application.fam")
    name = NAME_RE.search(text)
    icon = ICON_RE.search(text)
    category = CATEGORY_RE.search(text)
    version = ""
    match = FAP_VERSION_RE.search(text)
    if match:
        raw = match.group(1).strip().rstrip(",").strip()
        if raw.startswith("("):
            version = ".".join(re.findall(r"\d+", raw))
        else:
            version = raw.strip("\"").strip("'")
    return (
        appid.group(1),
        name.group(1) if name else appid.group(1),
        version,
        category_index(category.group(1) if category else None),
        os.path.join(appdir, icon.group(1)) if icon else None,
    )


def pack_icon(path):
    data = bytearray(ICON_BYTES)
    if path and os.path.isfile(path):
        image = Image.open(path).convert("1")
        if image.size != (ICON_DIM, ICON_DIM):
            image = image.resize((ICON_DIM, ICON_DIM))
        pixels = image.load()
        for y in range(ICON_DIM):
            row = 0
            for x in range(ICON_DIM):
                if pixels[x, y] == 0:
                    row |= 1 << x
            data[y * 2] = row & 0xFF
            data[y * 2 + 1] = row >> 8
    return bytes(data)


def build_app(appdir, appid):
    result = subprocess.run(["ufbt"], cwd=appdir, capture_output=True, text=True)
    print(result.stdout + result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"ufbt exited with {result.returncode}")
    faps = glob.glob(os.path.join(appdir, "dist", "*.fap"))
    if not faps:
        raise RuntimeError("no .fap produced")
    os.makedirs(DIST_DIR, exist_ok=True)
    shutil.copyfile(faps[0], os.path.join(DIST_DIR, f"{appid}.fap"))


def write_catalog(entries):
    strings_off = HEADER_SIZE + len(entries) * RECORD_SIZE
    pool = bytearray()
    records = bytearray()
    for appid, name, version, category, icon in entries:
        packed = []
        for value in (appid, name, version):
            raw = value.encode("utf-8")[:255]
            packed.append((strings_off + len(pool), len(raw)))
            pool += raw + b"\x00"
        records += struct.pack(
            "<IIIBBBB",
            packed[0][0], packed[1][0], packed[2][0],
            packed[0][1], packed[1][1], packed[2][1],
            category,
        )
        records += icon
    with open(CATALOG, "wb") as f:
        f.write(struct.pack("<4sBBHII", MAGIC, FORMAT_VERSION, RECORD_SIZE, len(entries), HEADER_SIZE, strings_off))
        f.write(records)
        f.write(pool)


def main():
    entries = []
    for appdir in sorted(set(glob.glob("apps/*") + glob.glob("apps/*/*"))):
        if not os.path.isdir(appdir) or not os.path.isfile(os.path.join(appdir, "application.fam")):
            continue
        try:
            appid, name, version, category, icon_path = read_fam(appdir)
            build_app(appdir, appid)
            entries.append((appid, name, version, category, pack_icon(icon_path)))
            print(f"built {appdir} -> {appid} {version} [{CATEGORIES[category]}]")
        except Exception as error:
            print(f"skip {appdir}: {error}")
    write_catalog(entries)
    print(f"catalog: {len(entries)} apps, {os.path.getsize(CATALOG)} bytes -> {CATALOG}")


if __name__ == "__main__":
    main()
