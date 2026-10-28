"""Add explicit server selection and safe response diagnostics to the helper."""
import pathlib, shutil
from prepare_gmr_login import replace_once

def prepare(source):
    app = pathlib.Path(source)/'GetMoreRam'
    runtime = pathlib.Path(__file__).resolve().parents[1]/'runtime/GMRServer.swift'
    shutil.copyfile(runtime, app/'GMRServer.swift')
    helper = app/'AnisetteDataHelper.swift'; text = helper.read_text()
    configure = '''
    @discardableResult
    func configureServer(_ input: String) throws -> Bool {
        let selected = try GMRServer.baseURL(input)
        let changed = url?.absoluteString != selected.absoluteString
        if changed {
            Keychain.shared.adiPb = nil
            Keychain.shared.identifier = nil
            resetClientInfo()
        }
        url = selected
        return changed
    }

    func checkServer(_ input: String) async throws -> String {
        try configureServer(input)
        var request = URLRequest(url: url!.appendingPathComponent("v3/client_info"))
        request.timeoutInterval = 15
        let (data, response) = try await URLSession.shared.data(for: request)
        _ = try GMRServer.clientInfo(data, response: response as? HTTPURLResponse)
        return "HTTP 200: v3 metadata is valid. This check does not test Apple sign-in."
    }
'''
    text = replace_once(text, '    func getAnisetteData(refresh: Bool = false)', configure+'\n    func getAnisetteData(refresh: Bool = false)')
    text = replace_once(text, '        if url == nil {', '        try configureServer(DataManager.shared.model.anisetteServerURL)\n        if url == nil {')
    old_json = 'if let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: String] {'
    if text.count(old_json) != 2: raise ValueError('Pinned parser context differs')
    text = text.replace(old_json, 'if let json = try GMRServer.object(data, response: response, stage: "Anisette v3 get_headers") as? [String: String] {', 1)
    start = text.index('        self.printOut("Using custom client_info")')
    end = text.index('        if Keychain.shared.identifier == nil {', start)
    text = text[:start]+'''        var metadataRequest = URLRequest(url: self.url!.appendingPathComponent("v3/client_info"))
        metadataRequest.timeoutInterval = 15
        let (metadata, response) = try await URLSession.shared.data(for: metadataRequest)
        let (client, agent) = try GMRServer.clientInfo(metadata, response: response as? HTTPURLResponse)
        self.clientInfo = client
        self.userAgent = agent
        self.printOut("Server v3 client metadata loaded")

'''+text[end:]
    # Remove obsolete, commented legacy metadata fetch.
    start = text.index('        // Client info on Anisette Servers are out of date')
    end = text.index('*/', start)+2
    text = text[:start]+text[end:]
    # Remove raw anisette material and server bodies from the on-screen logger.
    lines = text.splitlines()
    text = '\n'.join(line for line in lines if not any(token in line for token in ('Anisette used:', 'Original JSON:', 'Got response:', 'X-Apple-I-MD-LU:', 'X-Mme-Device-Id:')))+'\n'
    text = replace_once(text, 'self.printOut("Error getting V3 headers: \\(message ?? "no message")")', 'self.printOut("Anisette server reported a get_headers error")')
    # WebSocket protocol messages also need a stage-specific format error.
    text = replace_once(text, 'let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] else {', 'let json = (try? JSONSerialization.jsonObject(with: data, options: [])) as? [String: Any] else {')
    helper.write_text(text)
    shared = app/'Shared.swift'; text = shared.read_text().replace('var anisetteServerURL = "https://ani.sidestore.io"', 'var anisetteServerURL = "https://new.ani.sidestore.io"'); shared.write_text(text)
    settings = app/'SettingsView.swift'; text = settings.read_text()
    text = replace_once(text, '    @State private var errorShow = false', '    @State private var isCheckingServer = false\n    @State private var customServerMode = false\n    @State private var serverCheckResult = ""\n    @State private var errorShow = false')
    old = '''            Section {
                HStack {
                    Text("Anisette Server URL")
                    Spacer()
                    TextField("", text: $sharedModel.anisetteServerURL)
                        .multilineTextAlignment(.trailing)
                }
            }'''
    new = '''            Section {
                Picker("Server", selection: Binding(
                    get: { !customServerMode && GMRServer.presets.contains(where: { $0.address == sharedModel.anisetteServerURL }) ? sharedModel.anisetteServerURL : "custom" },
                    set: { selected in
                        if selected != "custom" {
                            customServerMode = false
                            sharedModel.anisetteServerURL = selected
                            applyServer()
                        } else { customServerMode = true }
                    }
                )) {
                    ForEach(GMRServer.presets, id: \\.address) { server in
                        Text(server.name).tag(server.address)
                    }
                    Text("Custom URL").tag("custom")
                }
                TextField("HTTPS server base URL", text: $sharedModel.anisetteServerURL)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .onSubmit { applyServer() }
                Button(isCheckingServer ? "Checking..." : "Check v3 Server") {
                    Task { await checkServer() }
                }
                .disabled(isCheckingServer)
                if !serverCheckResult.isEmpty { Text(serverCheckResult).font(.footnote) }
            } header: {
                Text("Anisette Server")
            } footer: {
                Text("Presets are from SideStore's official directory. Changing servers resets this helper's Anisette state and signs it out. The check sends no Apple account credentials.")
            }
            .disabled(viewModel.isLoginInProgress)'''
    text = replace_once(text, old, new)
    methods = '''
    func applyServer() {
        do {
            let normalized = try GMRServer.baseURL(sharedModel.anisetteServerURL).absoluteString
            let changed = try AnisetteDataHelper.shared.configureServer(normalized)
            sharedModel.anisetteServerURL = normalized
            serverCheckResult = ""
            if changed {
                sharedModel.session = nil
                sharedModel.account = nil
                sharedModel.team = nil
                sharedModel.isLogin = false
                viewModel.availableTeams = []
                viewModel.teamSelectionShow = false
                email = ""
                teamId = ""
            }
        } catch {
            errorInfo = error.detailedDescription
            errorShow = true
        }
    }

    func checkServer() async {
        applyServer()
        isCheckingServer = true
        defer { isCheckingServer = false }
        do {
            serverCheckResult = try await AnisetteDataHelper.shared.checkServer(sharedModel.anisetteServerURL)
        } catch {
            serverCheckResult = error.detailedDescription
        }
    }
'''
    text = replace_once(text, '    func cleanUp() {', methods+'\n    func cleanUp() {')
    settings.write_text(text)
    return {'server_presets': 4, 'v3_preflight_without_credentials': True, 'safe_anisette_response_diagnostics': True, 'server_change_resets_anisette_state': True}
