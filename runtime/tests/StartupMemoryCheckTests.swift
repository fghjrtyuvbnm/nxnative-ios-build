import Foundation
@main struct StartupMemoryCheckTests {
static func main() {
    precondition(StartupMemoryState(signature: 1, profile: 1).status == .present)
    precondition(StartupMemoryState(signature: 1, profile: 0).status == .missing)
    precondition(StartupMemoryState(signature: 0, profile: 1).status == .missing)
    precondition(StartupMemoryState(signature: -1, profile: 1).status == .unknown)
    precondition(StartupMemoryState(signature: -1, profile: -1).status == .unknown)
    precondition(StartupMemoryState(signature: 2, profile: 1).status == .unknown)
    precondition(StartupMemoryState.budget(available: 1024, footprint: 512) == 1536)
    precondition(StartupMemoryState.budget(available: 0, footprint: 512) == 512)
    precondition(StartupMemoryState.budget(available: UInt64.max, footprint: 1) == nil)
    precondition(StartupMemoryState.budget(available: 1024, footprint: nil) == nil)
    precondition(!StartupMemoryState(signature: 1, profile: 1).message.contains("effective"))
    print("Startup memory declaration states, unknown handling and advisory budget fixtures passed")
}}
