"""File Naming Checker: checks document file names against a naming convention.

Convention (dummy example): PROJ-DISC-TYPE-NNNN-Rnn.ext
  PROJ  3 capital letters           e.g. ABC
  DISC  discipline code from list   e.g. CIV
  TYPE  document type from list     e.g. DRG
  NNNN  4-digit serial              e.g. 0012
  Rnn   revision R00 to R99
  ext   allowed extension
Standard library only. Python 3.8+.
"""
import csv
import os
import re
import sys
from collections import defaultdict

DISCIPLINES = {"CIV", "ARC", "STR", "MEC", "ELE", "HSE", "QAC"}
DOC_TYPES = {"DRG", "RPT", "SPC", "MOM", "TRN", "PRC"}
EXTENSIONS = {"pdf", "docx", "xlsx", "dwg"}
# Heuristic note, not a failure: discipline is part of a document's identity,
# so the same serial under two disciplines can be legitimate. Set False to hide it.
NOTE_SERIAL_REUSE = True
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
PROJECT_RE = re.compile(r"^[A-Z]{3}$")
SERIAL_RE = re.compile(r"^\d{4}$")
REV_RE = re.compile(r"^R\d{2}$")


def check_name(filename):
    """Return a list of problems for one file name (empty list = OK)."""
    problems = []
    if CONTROL_RE.search(filename):
        problems.append("contains control character")
    name = filename
    if name != name.strip():
        problems.append("leading or trailing space")
        name = name.strip()
    if not name:
        return ["empty name"]
    if " " in name:
        problems.append("contains space")
    if "." not in name:
        problems.append("no extension")
        stem, ext = name, ""
    else:
        stem, ext = name.rsplit(".", 1)
        if ext != ext.lower():
            problems.append("extension not lower case")
        if ext.lower() not in EXTENSIONS:
            problems.append("extension not allowed: " + ext)
    parts = stem.split("-")
    if len(parts) != 5:
        problems.append("expected 5 fields, found %d" % len(parts))
        return problems
    proj, disc, dtype, serial, rev = parts
    if not PROJECT_RE.match(proj):
        problems.append("project code must be 3 capital letters")
    if disc not in DISCIPLINES:
        problems.append("unknown discipline: " + disc)
    if dtype not in DOC_TYPES:
        problems.append("unknown document type: " + dtype)
    if not SERIAL_RE.match(serial):
        problems.append("serial must be 4 digits")
    if not REV_RE.match(rev):
        problems.append("revision must look like R00")
    return problems


def check_all(filenames):
    """Return rows (filename, status, problems). Also flags duplicates."""
    rows = []
    seen = defaultdict(list)
    for i, f in enumerate(filenames):
        seen[f.strip().lower()].append(i)
    for i, f in enumerate(filenames):
        p = check_name(f)
        if len(seen[f.strip().lower()]) > 1:
            p.append("duplicate name")
        rows.append((f, "OK" if not p else "FAIL", "; ".join(p)))
    return rows


def serial_clashes(filenames):
    """Same project+type+serial under different disciplines (a heuristic note, not a failure)."""
    by = defaultdict(set)
    for f in filenames:
        parts = f.strip().rsplit(".", 1)[0].split("-")
        if len(parts) == 5:
            by[(parts[0], parts[2], parts[3])].add(parts[1])
    return sorted(k for k, v in by.items() if len(v) > 1)


def csv_safe(value):
    """Make a cell safe to open in Excel: a leading = + - @ tab or CR (or any
    control character) would be read as a formula, so prefix it with an
    apostrophe. Used for export only; raw names are kept elsewhere."""
    text = str(value)
    if text and (text[0] in "=+-@\t\r" or CONTROL_RE.match(text)):
        return "'" + text
    return text


def show(value):
    """Printable form of a name: control characters shown as escapes."""
    return CONTROL_RE.sub(lambda m: "\\x%02x" % ord(m.group()), value)


def same_path(a, b):
    a, b = os.path.abspath(a), os.path.abspath(b)
    if os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b)):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def write_report(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as out:
        w = csv.writer(out)
        w.writerow(["filename", "status", "problems"])
        for f, status, p in rows:
            w.writerow([csv_safe(f), status, csv_safe(p)])


def main(argv):
    if len(argv) not in (2, 3):
        print("usage: python namecheck.py names.txt [report.csv]", file=sys.stderr)
        return 2
    if len(argv) == 3 and same_path(argv[1], argv[2]):
        print("error: report path is the same as the input file; choose another name", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8-sig") as fh:
            names = [ln.rstrip("\r\n") for ln in fh if ln.strip()]
    except OSError as e:
        print("error: cannot read %s: %s" % (argv[1], e.strerror or e), file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("error: %s is not valid UTF-8; save it as UTF-8 and try again" % argv[1], file=sys.stderr)
        return 2
    rows = check_all(names)
    bad = [r for r in rows if r[1] == "FAIL"]
    print("Checked %d names: %d OK, %d FAIL" % (len(rows), len(rows) - len(bad), len(bad)))
    for f, _, p in bad:
        print("  FAIL  %s  ->  %s" % (show(f), p))
    if NOTE_SERIAL_REUSE:
        for k in serial_clashes(names):
            print("  NOTE  serial %s-%s-%s is used under more than one discipline "
                  "(may be fine; not counted as a failure)" % k)
    if len(argv) == 3:
        try:
            write_report(argv[2], rows)
        except OSError as e:
            print("error: cannot write %s: %s" % (argv[2], e.strerror or e), file=sys.stderr)
            return 2
        print("Report written to " + argv[2])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
