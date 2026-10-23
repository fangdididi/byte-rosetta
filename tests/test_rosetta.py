import contextlib, io, json, os, random, shutil, struct, sys, tempfile, unittest, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "examples"))
import rosetta  # noqa: E402
import make_samples  # noqa: E402

SPEC = os.path.join(ROOT, "examples", "moss-harbor.spec.json")
LABELS = os.path.join(ROOT, "examples", "labels.csv")


def rb(p):
    with open(p, "rb") as f:
        return f.read()


def wb(p, data, mode="wb"):
    with open(p, mode) as f:
        f.write(data)


def spec():
    with open(SPEC, encoding="utf-8") as f:
        return json.load(f)


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = rosetta.main(list(argv))
    return code, buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with contextlib.redirect_stdout(io.StringIO()):
            make_samples.main(self.tmp)
        self.s = lambda n: os.path.join(self.tmp, n)
        self.all = sorted(os.path.join(self.tmp, f) for f in os.listdir(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestSpec(Base):
    def test_check_passes_all_samples_with_labels(self):
        code, out = run("check", SPEC, *self.all, "--labels", LABELS)
        self.assertEqual(code, 0, out)
        self.assertIn("6/6 samples pass", out)

    def test_wrong_label_fails(self):
        bad = os.path.join(self.tmp, "bad.csv")
        wb(bad, b"file,field,value\ns01_base_a.mhs,coins,121\n")
        code, out = run("check", SPEC, self.s("s01_base_a.mhs"), "--labels", bad)
        self.assertEqual(code, 1)
        self.assertIn("LABEL coins", out)

    def test_uncovered_tail_is_reported(self):
        p = self.s("s01_base_a.mhs")
        wb(p, b"\x00\x00", "ab")
        code, out = run("check", SPEC, p)
        self.assertEqual(code, 1)
        self.assertIn("COVERAGE 2 byte(s)", out)

    def test_broken_seal_is_reported(self):
        p = self.s("s03_coins_125.mhs")
        d = bytearray(rb(p))
        d[11] ^= 0x01
        wb(p, d)
        code, out = run("check", SPEC, p)
        self.assertEqual(code, 1)
        self.assertIn("SEAL seal", out)

    def test_const_mismatch(self):
        p = self.s("s01_base_a.mhs")
        d = bytearray(rb(p))
        d[0] = ord("X")
        wb(p, d)
        code, out = run("check", SPEC, p)
        self.assertIn("CONST magic", out)

    def test_mirror_and_coverage_numbers(self):
        sp = spec()
        data = rb(self.s("s06_new_rod.mhs"))
        tree, rd, problems, named, gap, proof = rosetta.analyse(sp, data)
        self.assertEqual(problems, [])
        self.assertEqual(named + gap, len(data))
        self.assertEqual(rosetta.Writer(sp).run(tree), data)
        self.assertEqual(tree["catches"][2]["weight_g"], 2210)

    def test_short_file_raises_clear_error(self):
        p = self.s("s01_base_a.mhs")
        wb(p, rb(p)[:10])
        code, out = run("check", SPEC, p)
        self.assertEqual(code, 1)
        self.assertIn("needs", out)


class TestSet(Base):
    def test_set_number_refreshes_seal(self):
        out = os.path.join(self.tmp, "edit.bin")
        code, text = run("set", SPEC, self.s("s01_base_a.mhs"), "coins", "999", "--out", out)
        self.assertEqual(code, 0, text)
        sp = spec()
        tree, _, problems, *_ = rosetta.analyse(sp, rb(out))
        self.assertEqual(tree["coins"], 999)
        self.assertEqual(problems, [])

    def test_set_string_updates_length(self):
        out = os.path.join(self.tmp, "edit.bin")
        code, text = run("set", SPEC, self.s("s01_base_a.mhs"), "name", "Bo", "--out", out)
        self.assertEqual(code, 0, text)
        tree, _, problems, *_ = rosetta.analyse(spec(), rb(out))
        self.assertEqual((tree["name"], tree["name_len"]), ("Bo", 2))

    def test_set_repeated_item(self):
        out = os.path.join(self.tmp, "edit.bin")
        code, _ = run("set", SPEC, self.s("s06_new_rod.mhs"), "catches[1].weight_g", "1000", "--out", out)
        self.assertEqual(code, 0)
        tree, *_ = rosetta.analyse(spec(), rb(out))
        self.assertEqual(tree["catches"][1]["weight_g"], 1000)

    def test_set_refuses_to_overwrite_input(self):
        p = self.s("s01_base_a.mhs")
        before = rb(p)
        code, out = run("set", SPEC, p, "coins", "5", "--out", p)
        self.assertEqual(code, 2)
        self.assertEqual(rb(p), before)

    def test_set_value_out_of_range(self):
        out = os.path.join(self.tmp, "edit.bin")
        code, text = run("set", SPEC, self.s("s01_base_a.mhs"), "catch_count", "70000", "--out", out)
        self.assertEqual(code, 2)


class TestProbes(Base):
    def test_seal_finds_crc32(self):
        code, out = run("seal", *self.all, "--at", "-4", "--width", "4")
        self.assertEqual(code, 0)
        self.assertIn("crc32", out)
        self.assertIn("before-field", out)
        self.assertNotIn("only", out)

    def test_seal_warns_with_few_samples(self):
        code, out = run("seal", self.s("s01_base_a.mhs"), "--at", "-4", "--width", "4")
        self.assertIn("coincidence", out)

    def test_seal_known_algorithms(self):
        self.assertEqual(rosetta.seal_value("crc16-ccitt-false", b"123456789"), 0x29B1)
        self.assertEqual(rosetta.seal_value("crc16-xmodem", b"123456789"), 0x31C3)
        self.assertEqual(rosetta.seal_value("crc16-arc", b"123456789"), 0xBB3D)
        self.assertEqual(rosetta.seal_value("crc16-modbus", b"123456789"), 0x4B37)
        self.assertEqual(rosetta.seal_value("crc32", b"123456789"), 0xCBF43926)
        self.assertEqual(rosetta.seal_value("fletcher16", b"abcde"), 0xC8F0)

    def test_diff_marks_twin_noise(self):
        code, out = run("diff", self.s("s01_base_a.mhs"), self.s("s03_coins_125.mhs"),
                        "--twins", self.s("s01_base_a.mhs"), self.s("s02_base_b.mhs"))
        self.assertIn("SIGNAL 0x00000b", out)
        self.assertIn("120->125", out)
        self.assertIn("NOISE ", out)
        self.assertIn("NOISE? 0x00000f", out)

    def test_find_locates_coins(self):
        code, out = run("find", self.s("s03_coins_125.mhs"), "125")
        self.assertIn("0xb", out)
        code, out = run("find", self.s("s05_long_name.mhs"), "Reeds")
        self.assertIn("utf-8", out)

    def test_find_float_and_scaled(self):
        p = os.path.join(self.tmp, "f.bin")
        wb(p, b"\x00" * 3 + struct.pack("<f", 12.5) + struct.pack("<H", 1250))
        code, out = run("find", p, "12.5", "--float")
        self.assertIn("f32le", out)
        self.assertIn("u16lex100", out)

    def test_survey_flags_packed_and_sealed(self):
        rnd = random.Random(7)
        text = (" ".join(rnd.choice(["reed", "pond", "eel", "moss"]) for _ in range(3000))).encode()
        packed = os.path.join(self.tmp, "packed.bin")
        wb(packed, b"HDR!" + bytes(252) + zlib.compress(bytes(rnd.getrandbits(8) for _ in range(4000))))
        noise = os.path.join(self.tmp, "noise.bin")
        wb(noise, bytes(rnd.getrandbits(8) for _ in range(2048)))
        code, out = run("survey", packed, noise)
        self.assertIn("PACKED (zlib", out)
        self.assertIn("SEALED?", out)
        zipish = os.path.join(self.tmp, "z.bin")
        wb(zipish, b"PK\x03\x04" + text[:300])
        code, out = run("survey", zipish)
        self.assertIn("KNOWN SIGNATURE: zip", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
