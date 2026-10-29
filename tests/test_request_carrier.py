import pathlib, plistlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from request_carrier import validate_requests, canonical_request

class RequestCarrierTests(unittest.TestCase):
    def test_exact_boolean_requests(self):
        keys = ('com.apple.developer.kernel.increased-memory-limit',)
        validate_requests(dict.fromkeys(keys, True))
        for invalid in ({}, dict.fromkeys(keys, 1), dict.fromkeys(keys, False), dict(dict.fromkeys(keys, True), extra=True), dict(dict.fromkeys(keys, True), **{'com.apple.developer.kernel.extended-virtual-addressing': True})):
            with self.assertRaises(ValueError): validate_requests(invalid)

    def test_shipped_plist_matches_single_permission_policy(self):
        value = plistlib.loads((pathlib.Path(__file__).resolve().parents[1]/'runtime/MemoryRequirements.entitlements').read_bytes())
        self.assertEqual(value, {'com.apple.developer.kernel.increased-memory-limit': True})

    def test_native_request_uses_canonical_xml_without_crlf(self):
        value = {'com.apple.developer.kernel.increased-memory-limit': True}
        source = plistlib.dumps(value).replace(b'\n', b'\r\n')
        output = canonical_request(source)
        self.assertNotIn(b'\r', output)
        self.assertEqual(output, plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=True))

if __name__ == '__main__': unittest.main()
