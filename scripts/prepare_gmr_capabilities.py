"""Decode structured capability errors and verify the target App ID after updates."""
import pathlib, shutil
from prepare_gmr_login import replace_once

def prepare(source, dependency):
    source, dependency = pathlib.Path(source), pathlib.Path(dependency)
    kit = pathlib.Path(__file__).resolve().parents[1]
    for name in ('GMRCapabilityResponse.swift', 'GMRMemoryCapabilities.swift'):
        shutil.copyfile(kit/'runtime'/name, dependency/'Sources/StosSign_Common'/name)
    model = dependency/'Sources/StosSign_Common/Models/Apple API/AppID.swift'; text = model.read_text()
    text = replace_once(text, '    public var entitlements: [String]', '    public var entitlements: [String]\n    public var enabledFeatureIdentifiers: [String] = []\n    public var capabilityUpdateReceipt: String? = nil')
    text = replace_once(text, 'self.init(name: name, identifier: identifier, bundleIdentifier: bundleIdentifier, expirationDate: expirationDate, features: features)', 'self.init(name: name, identifier: identifier, bundleIdentifier: bundleIdentifier, expirationDate: expirationDate, features: features)\n        self.enabledFeatureIdentifiers = enabledFeatures')
    model.write_text(text)
    api = dependency/'Sources/StosSign_API/AppleAPI.swift'; text = api.read_text()
    start = text.index('    public func sendEditRequest('); end = text.index('    public func sendRequestWithURL(', start)
    part = text[start:end]
    part = replace_once(part, 'let (data, _) = try await self.session.data(for: request)', 'let (data, response) = try await self.session.data(for: request)')
    part = replace_once(part, '''guard let responseDictionary = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] else {
                throw AppleAPIError.badServerResponse
            }
            
            return responseDictionary''', '''return try GMRCapabilityResponse.object(data, response: response)''')
    text = text[:start]+part+text[end:]
    start = text.index('    public func updateAppID(_ appID: AppID, capabilities:')
    end = text.index('    public func qHupdateAppID(', start)
    part = text[start:end]
    begin = part.index('        print("Server Response:')
    finish = part.index('        return appID', begin)
    part = part[:begin]+'        try GMRCapabilityResponse.requireUpdateResource(response)\n\n'+part[finish:]
    part = replace_once(part, '        return appID', '        var updated = appID\n        updated.capabilityUpdateReceipt = GMRCapabilityResponse.receipt(response)\n        return updated')
    text = text[:start]+part+text[end:]; api.write_text(text)
    app = source/'GetMoreRam'
    model = app/'AppIDViewModel.swift'; text = model.read_text()
    text = replace_once(text, '    @Published var result: String = ""', '    @Published var result: String = ""\n    @Published var isUpdating = false')
    start = text.index('    func addIncreasedMemory() async throws {')
    end = text.index('\n    \n}', start)
    text = text[:start]+'''    func readTarget(team: Team, session: AppleAPISession) async throws -> AppID {
        let ids = try await AppleAPI.shared.fetchAppIDsForTeam(team: team, session: session)
        guard let current = ids.first(where: { $0.identifier == appID.identifier && $0.bundleIdentifier == appID.bundleIdentifier }) else {
            throw GMRAuthResponseError("Apple memory capability readback: target App ID is not in this team's refreshed listing.")
        }
        return current
    }

    @MainActor
    func addIncreasedMemory(_ selection: GMRMemoryCapabilities.Selection = .increased) async throws {
        guard !isUpdating else { return }
        guard let team = DataManager.shared.model.team, let session = DataManager.shared.model.session else { throw "Please Login First" }
        isUpdating = true
        result = "Reading current capability state..."
        defer {
            isUpdating = false
            if result == "Reading current capability state..." { result = "Capability state was not confirmed. See the error details." }
        }
        var responseReceipt: String?
        let (verified, message) = try await GMRMemoryCapabilities.apply(selection,
            read: { try await self.readTarget(team: team, session: session) },
            update: { current in
                let response = try await AppleAPI.shared.updateAppID(current, capabilities: selection.identifiers, team: team, session: session)
                responseReceipt = response.capabilityUpdateReceipt
            }
        )
        appID = verified
        result = message + (responseReceipt.map { "\\n\\n" + $0 } ?? "")
    }

    @MainActor
    func checkMemoryCapabilities() async throws {
        guard !isUpdating else { return }
        guard let team = DataManager.shared.model.team, let session = DataManager.shared.model.session else { throw "Please Login First" }
        isUpdating = true
        result = "Capability state was not confirmed. Checking..."
        defer { isUpdating = false }
        appID = try await readTarget(team: team, session: session)
        result = GMRMemoryCapabilities.summary(appID) + ". This checks App ID configuration, not an installed provisioning profile."
    }
'''+text[end:]
    model.write_text(text)
    view = app/'AppIDView.swift'; text = view.read_text()
    text = replace_once(text, '                    Text("Add Both Memory Capabilities")\n                }', '''                    Text(viewModel.isUpdating ? "Checking..." : "Add Increased Memory Limit")
                }
                .disabled(viewModel.isUpdating)
                DisclosureGroup("Paid account options") {
                    Text("Extended Virtual Addressing is excluded from the default action. Use this separate action only for the paid account path.")
                    Button("Add Extended Virtual Addressing Only") {
                        Task {
                            do { try await viewModel.addIncreasedMemory(.extended) }
                            catch { errorInfo = error.detailedDescription; errorShow = true }
                        }
                    }
                    .disabled(viewModel.isUpdating)
                }
                Button("Check Memory Capabilities") {
                    Task {
                        do { try await viewModel.checkMemoryCapabilities() }
                        catch { errorInfo = error.detailedDescription; errorShow = true }
                    }
                }
                .disabled(viewModel.isUpdating)''')
    view.write_text(text)
    return {'capability_http_and_json_errors_preserved': True, 'memory_capability_readback_required': True, 'unrelated_enabled_feature_readback_checked': True, 'both_capabilities_submitted_together': False, 'default_increased_memory_only': True, 'extended_requires_separate_action': True, 'safe_server_reason_classification': True, 'accepted_but_unconfirmed_is_warning': True, 'safe_update_receipt_separated': True}
