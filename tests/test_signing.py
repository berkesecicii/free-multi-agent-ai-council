import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SigningTests(unittest.TestCase):
    def test_build_uses_the_fixed_identity_when_it_exists_and_falls_back_to_ad_hoc(self):
        build=(ROOT/'native'/'build.sh').read_text(encoding='utf-8');setup=(ROOT/'Imza-kur.command').read_text(encoding='utf-8')
        name='JARVIS Local Signing'
        self.assertIn(name,build);self.assertIn(name,setup)                       # one name in both places
        self.assertIn("identity='-'",build);self.assertIn("'--sign',identity",build) # ad hoc is the default and the fallback
        self.assertIn('timeout=120',build);self.assertIn('TimeoutExpired',build)    # an unanswered key-access prompt cannot hang the build
        self.assertIn("codesign','--verify','--deep'",build)
    def test_setup_script_never_stores_or_asks_for_the_mac_password(self):
        setup=(ROOT/'Imza-kur.command').read_text(encoding='utf-8')
        self.assertIn('security add-trusted-cert',setup);self.assertIn('-p codeSign',setup)
        for forbidden in ('read -s','sudo ','set-key-partition-list','security unlock-keychain'):self.assertNotIn(forbidden,setup)
        self.assertIn('OSSL=/usr/bin/openssl',setup);self.assertNotIn('\nopenssl ',setup)   # system LibreSSL only; Homebrew OpenSSL 3 makes .p12 files the Keychain rejects
        self.assertIn('trap',setup);self.assertIn('rm -rf "$TMP"',setup)           # the private key file never stays on disk
if __name__=='__main__':unittest.main()
