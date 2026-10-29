"""Native synthetic policy checks; never inspect a real profile or Apple account."""
import pathlib,subprocess,sys

def main(out):
    kit=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    binary=out/'startup-memory-policy'
    subprocess.run(['swiftc','-parse-as-library',str(kit/'runtime/StartupMemoryState.swift'),str(kit/'runtime/tests/StartupMemoryCheckTests.swift'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
    sdk=subprocess.check_output(['xcrun','--sdk','iphoneos','--show-sdk-path'],text=True).strip()
    subprocess.run(['xcrun','swiftc','-typecheck','-target','arm64-apple-ios18.0','-sdk',sdk,str(kit/'runtime/StartupMemoryState.swift'),str(kit/'runtime/StartupMemoryView.swift')],check=True)
    print('iOS 18 startup-memory SwiftUI typecheck passed',flush=True)

if __name__=='__main__':main(sys.argv[1])
