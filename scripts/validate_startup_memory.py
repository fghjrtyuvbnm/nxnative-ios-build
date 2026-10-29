"""Native synthetic policy checks; never inspect a real profile or Apple account."""
import pathlib,subprocess,sys

def main(out):
    kit=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    binary=out/'startup-memory-policy'
    subprocess.run(['swiftc','-parse-as-library',str(kit/'runtime/StartupMemoryState.swift'),str(kit/'runtime/tests/StartupMemoryCheckTests.swift'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

if __name__=='__main__':main(sys.argv[1])
