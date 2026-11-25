import csv, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import namecheck as n


class T(unittest.TestCase):
    def ok(self, f): self.assertEqual(n.check_name(f), [], f)
    def bad(self, f, text):
        self.assertTrue(any(text in p for p in n.check_name(f)), (f, n.check_name(f)))

    def test_valid(self):
        self.ok("ABC-CIV-DRG-0001-R00.pdf"); self.ok("XYZ-QAC-TRN-9999-R99.xlsx")
    def test_lower_project(self): self.bad("abc-CIV-DRG-0004-R00.pdf", "project code")
    def test_short_revision(self): self.bad("ABC-CIV-DRG-0005-R0.pdf", "revision")
    def test_bad_discipline(self): self.bad("ABC-XYZ-DRG-0006-R00.pdf", "discipline")
    def test_bad_type(self): self.bad("ABC-CIV-ZZZ-0006-R00.pdf", "document type")
    def test_upper_ext(self): self.bad("ABC-ELE-DRG-0007-R00.PDF", "lower case")
    def test_space(self): self.bad("ABC-HSE-MOM-0008-R00 final.docx", "space")
    def test_short_serial(self): self.bad("ABC-QAC-TRN-009-R00.pdf", "serial")
    def test_missing_field(self): self.bad("ABC-CIV-DRG-0010.pdf", "5 fields")
    def test_ext_not_allowed(self): self.bad("ABC-CIV-DRG-0013-R00.exe", "not allowed")
    def test_no_ext(self): self.bad("ABC-CIV-DRG-0014-R00", "no extension")
    def test_empty(self): self.assertEqual(n.check_name("   "), ["empty name"])
    def test_trailing_space(self): self.bad("ABC-CIV-DRG-0001-R00.pdf ", "trailing")
    def test_extra_dashes(self): self.bad("ABC-CIV-DRG-0001-R00-final.pdf", "5 fields")
    def test_duplicates_case_insensitive(self):
        r = n.check_all(["ABC-CIV-DRG-0001-R00.pdf", "abc-civ-drg-0001-r00.PDF"])
        self.assertTrue(all("duplicate" in x[2] for x in r))
    def test_revisions_not_duplicates(self):
        r = n.check_all(["ABC-CIV-DRG-0001-R00.pdf", "ABC-CIV-DRG-0001-R01.pdf"])
        self.assertTrue(all(x[1] == "OK" for x in r))
    def test_serial_clash(self):
        self.assertEqual(n.serial_clashes(["ABC-STR-PRC-0012-R00.pdf", "ABC-CIV-PRC-0012-R00.pdf"]), [("ABC", "PRC", "0012")])
    def test_no_clash_for_revisions(self):
        self.assertEqual(n.serial_clashes(["ABC-CIV-DRG-0001-R00.pdf", "ABC-CIV-DRG-0001-R01.pdf"]), [])
    def test_empty_list(self): self.assertEqual(n.check_all([]), [])

    def test_control_char(self): self.bad("ABC-CIV-DRG-0001-R00\x07.pdf", "control")
    def test_csv_safe_prefixes(self):
        for v in ["=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx", "\x07x"]:
            self.assertEqual(n.csv_safe(v)[0], "'", repr(v))
        self.assertEqual(n.csv_safe("ABC-CIV"), "ABC-CIV")
        self.assertEqual(n.csv_safe(""), "")

    def test_export_escapes_but_raw_kept(self):
        names = ["=HYPERLINK(1).pdf", "ABC-CIV-DRG-0001-R00.pdf"]
        rows = n.check_all(names)
        self.assertEqual(rows[0][0], "=HYPERLINK(1).pdf")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.csv")
            n.write_report(p, rows)
            with open(p, encoding="utf-8-sig", newline="") as fh:
                out = list(csv.reader(fh))
        self.assertEqual(out[1][0], "'=HYPERLINK(1).pdf")
        for r in out[1:]:
            for cell in r:
                self.assertNotIn(cell[:1], list("=+-@"))

    def test_same_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt"); open(p, "w").close()
            self.assertTrue(n.same_path(p, os.path.join(d, ".", "a.txt")))
            self.assertTrue(n.same_path(p, os.path.join(d, "sub", "..", "a.txt")))
            self.assertFalse(n.same_path(p, os.path.join(d, "b.csv")))
            ln = os.path.join(d, "link.txt"); os.symlink(p, ln)
            self.assertTrue(n.same_path(p, ln))


def run(*args):
    return subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "..", "namecheck.py")] + list(args),
                          capture_output=True, text=True)


class CLI(unittest.TestCase):
    def test_refuses_overwrite_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "names.txt")
            with open(p, "w") as fh: fh.write("ABC-CIV-DRG-0001-R00.pdf\n")
            r = run(p, p)
            self.assertEqual(r.returncode, 2)
            self.assertIn("same as the input", r.stderr)
            with open(p) as fh: self.assertEqual(fh.read(), "ABC-CIV-DRG-0001-R00.pdf\n")

    def test_bom_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "n.txt")
            with open(p, "wb") as fh: fh.write(b"\xef\xbb\xbfABC-CIV-DRG-0001-R00.pdf\r\n")
            r = run(p)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 OK, 0 FAIL", r.stdout)

    def test_missing_file(self):
        r = run("/nonexistent/x.txt")
        self.assertEqual(r.returncode, 2); self.assertIn("error:", r.stderr); self.assertNotIn("Traceback", r.stderr)

    def test_bad_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "n.txt")
            with open(p, "wb") as fh: fh.write(b"ABC\xff\xfe.pdf\n")
            r = run(p)
            self.assertEqual(r.returncode, 2); self.assertNotIn("Traceback", r.stderr)

    def test_unwritable_report(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "n.txt")
            with open(p, "w") as fh: fh.write("ABC-CIV-DRG-0001-R00.pdf\n")
            r = run(p, os.path.join(d, "nodir", "r.csv"))
            self.assertEqual(r.returncode, 2); self.assertNotIn("Traceback", r.stderr)

    def test_serial_note_not_a_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "n.txt")
            with open(p, "w") as fh: fh.write("ABC-STR-PRC-0012-R00.pdf\nABC-CIV-PRC-0012-R00.pdf\n")
            r = run(p)
            self.assertEqual(r.returncode, 0); self.assertIn("NOTE", r.stdout); self.assertIn("2 OK, 0 FAIL", r.stdout)

    def test_no_args(self):
        self.assertEqual(run().returncode, 2)


if __name__ == "__main__":
    unittest.main()
