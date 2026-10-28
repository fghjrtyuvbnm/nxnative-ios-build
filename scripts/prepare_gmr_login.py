"""Adapt the pinned login repair while retaining the two Extended actions."""
import pathlib, re

DEPENDENCY = 'fcce0735c37368a64937cf37948dd34b3e23b07a'

def replace_once(text, old, new):
    if text.count(old) != 1: raise ValueError('Pinned source patch context differs')
    return text.replace(old, new)

def prepare(source, dependency):
    source, dependency = pathlib.Path(source), pathlib.Path(dependency)
    project = source/'GetMoreRam.xcodeproj/project.pbxproj'
    text = project.read_text()
    text = replace_once(text, 'repositoryURL = "https://github.com/no1ce21/StosSign";\n\t\t\trequirement = {\n\t\t\t\tbranch = main;\n\t\t\t\tkind = branch;\n\t\t\t};', 'relativePath = LoginStosSign;')
    # Only this project contains one package reference.
    text = text.replace('XCRemoteSwiftPackageReference', 'XCLocalSwiftPackageReference')
    project.write_text(text)
    app = source/'GetMoreRam'
    login = app/'LoginViewModel.swift'; text = login.read_text()
    text = replace_once(text, 'try await AppleAPI.shared.authenticate(appleID: appleID, password: password, anisetteData: anisetteData) { [weak self] completionHandler in', 'try await Authentication.authenticate(appleID: appleID, password: password, anisetteData: anisetteData, verificationHandler: { [weak self] completionHandler in')
    text = replace_once(text, 'self.prepareForVerification(using: completionHandler)\n            }', 'self.prepareForVerification(using: completionHandler)\n            }, anisetteDataRefreshHandler: {\n                try await AnisetteDataHelper.shared.getAnisetteData(refresh: true)\n            })')
    login.write_text(text)
    model = app/'AppIDViewModel.swift'; text = model.read_text()
    text = text.replace('capabilities: ["INCREASED_MEMORY_LIMIT"]', 'capabilities: ["INCREASED_MEMORY_LIMIT", "EXTENDED_VIRTUAL_ADDRESSING"]')
    if 'EXTENDED_VIRTUAL_ADDRESSING' not in text: raise ValueError('Capability patch failed')
    text = text.replace('result = "\\(cool)"', 'result = "Both memory capability requests submitted. Reinstall the target IPA, then verify its installed signature and profile."')
    # Avoid a misleading unused successful response variable.
    text = text.replace('let cool = try await AppleAPI.shared.updateAppID', '_ = try await AppleAPI.shared.updateAppID')
    model.write_text(text)
    view = app/'AppIDView.swift'; text = view.read_text().replace('Add Increased Memory Limit', 'Add Both Memory Capabilities'); view.write_text(text)
    # Keep app data / SideStore identity stable across the helper update.
    shared = app/'Shared.swift'; text = shared.read_text()
    if 'class DataManager' not in text: raise ValueError('Unexpected shared state')
    # Upstream detailedDescription is already implemented and used by Settings.
    if 'var detailedDescription' not in text: raise ValueError('Detailed errors missing')
    auth = dependency/'Sources/StosSign_Auth/Authentication.swift'
    if 'isCodeAlreadySent' not in auth.read_text() or 'anisetteDataRefreshHandler' not in auth.read_text():
        raise ValueError('Required authentication fixes missing')
    return {'login_reference': 'https://github.com/no1ce21/GetMoreRam', 'authentication_commit': DEPENDENCY,
            'extended_origin': 'https://github.com/Loganbogan9/GetMoreRamExtended/tree/a176a5c0271af8f462170065132021fb683b1706',
            'both_capabilities_submitted_together': True, 'fresh_anisette_callback_connected': True}
