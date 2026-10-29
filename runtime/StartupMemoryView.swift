import SwiftUI
import os

@_silgen_name("dm_startup_memory_flags") private func signingFlags() -> Int32
@_silgen_name("dm_startup_memory_footprint") private func processFootprint() -> UInt64

struct StartupMemoryView: View {
    @State private var state = StartupMemoryState(signature: -1, profile: -1)
    @State private var available: UInt64 = 0
    @State private var footprint: UInt64?

    private func refreshSigning() {
        let bits = signingFlags()
        state = StartupMemoryState(signature: (bits & 3) - 1, profile: ((bits >> 2) & 3) - 1)
        fputs("[memory-check-ui] signature_memory=\(state.signature) profile_memory=\(state.profile)\n", stderr)
    }
    private func refreshAllowance() {
        available = UInt64(os_proc_available_memory())
        let bytes = processFootprint()
        footprint = bytes == UInt64.max ? nil : bytes
    }
    private func size(_ bytes: UInt64) -> String { String(format: "%.0f MiB", Double(bytes) / 1048576) }
    var body: some View {
        Section("Startup memory check") {
            Label(state.message, systemImage: state.status == .present ? "checkmark.shield" : "exclamationmark.triangle")
                .foregroundStyle(state.status == .present ? Color.green : Color.orange)
            LabeledContent("App signature", value: StartupMemoryState.flag(state.signature))
            LabeledContent("Provisioning profile", value: StartupMemoryState.flag(state.profile))
            LabeledContent("Memory available now", value: size(available))
            if let budget = StartupMemoryState.budget(available: available, footprint: footprint) {
                LabeledContent("Estimated process limit now", value: size(budget))
            }
            Button("Check memory again") { refreshSigning(); refreshAllowance() }
        } footer: {
            Text("Signing declarations and current system allowance are separate checks. The allowance can change; it does not prove why a limit was granted. No allocation stress test is performed. Extended Virtual Addressing is not requested. You can still choose Play.")
        }
        .onAppear { refreshSigning(); refreshAllowance() }
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(2))
                if Task.isCancelled { break }
                refreshAllowance()
            }
        }
    }
}
