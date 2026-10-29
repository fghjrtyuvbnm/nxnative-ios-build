import pathlib, plistlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from request_carrier import validate_requests

class RequestCarrierTests(unittest.TestCase):
    def test_exact_boolean_requests(self):
        keys = ('com.apple.developer.kernel.increased-memory-limit',)
        validate_requests(dict.fromkeys(keys, True))
        for invalid in ({}, dict.fromkeys(keys, 1), dict.fromkeys(keys, False), dict(dict.fromkeys(keys, True), extra=True), dict(dict.fromkeys(keys, True), **{'com.apple.developer.kernel.extended-virtual-addressing': True})):
            with self.assertRaises(ValueError): validate_requests(invalid)

    def test_shipped_plist_matches_single_permission_policy(self):
        value = plistlib.loads((pathlib.Path(__file__).resolve().parents[1]/'runtime/MemoryRequirements.entitlements').read_bytes())
        self.assertEqual(value, {'com.apple.developer.kernel.increased-memory-limit': True})

if __name__ == '__main__': unittest.main()
