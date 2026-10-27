import Foundation

final class Bookmarks: GameDataBookmarks {
    var data: Data?; var reject = false
    func read() -> Data? { data }
    func write(_ data: Data) throws { if reject { throw GameDataError.unavailable }; self.data = data }
}
final class Access: GameDataAccess {
    var events: [String] = []; var denied = Set<String>(); var missing = Set<String>(); var corrupt = false
    var coordinatedRoot: URL?
    func resolve(_ data: Data) throws -> URL {
        if corrupt { throw GameDataError.invalidManifest }
        return URL(fileURLWithPath: String(data: data, encoding: .utf8)!)
    }
    func begin(_ u: URL) -> Bool { events.append("begin:" + u.path); return !denied.contains(u.path) }
    func end(_ u: URL) { events.append("end:" + u.path) }
    func bookmark(_ u: URL) throws -> Data { Data(u.path.utf8) }
    func inspect(_ u: URL, full: Bool, progress: ((Int, Int) -> Void)?) throws -> GameDataLayout {
        events.append("inspect:" + u.path)
        if missing.contains(u.path) { throw GameDataError.unavailable }
        return GameDataLayout(root: coordinatedRoot ?? u)
    }
}
func expectFailure(_ work: () throws -> Void) { do { try work(); fatalError("Expected failure") } catch {} }

@main struct Tests {
    static func main() throws {
        let a = Access(), bookmarks = Bookmarks(), first = URL(fileURLWithPath: "/fixture/a"), second = URL(fileURLWithPath: "/fixture/b")
        var session: GameDataSession? = GameDataSession(access: a, bookmarks: bookmarks)
        expectFailure { _ = try session!.restore() }
        _ = try session!.select(first)
        let original = bookmarks.data
        a.missing.insert(second.path)
        expectFailure { _ = try session!.select(second) }
        assert(session!.current?.root == first && bookmarks.data == original)
        assert(a.events.last == "end:" + second.path)
        a.missing.remove(second.path); bookmarks.reject = true
        expectFailure { _ = try session!.select(second) }
        assert(session!.current?.root == first && bookmarks.data == original)
        bookmarks.reject = false; a.denied.insert(second.path)
        let endsBefore = a.events.filter { $0.hasPrefix("end:") }.count
        expectFailure { _ = try session!.select(second) }
        assert(a.events.filter { $0.hasPrefix("end:") }.count == endsBefore)
        a.denied.remove(second.path)
        a.missing.insert(first.path); var launches = 0
        expectFailure { try session!.start { _ in launches += 1 } }
        assert(launches == 0 && !session!.started && bookmarks.data == original)
        a.missing.remove(first.path)
        expectFailure { try session!.start { _ in throw GameDataError.environment } }
        assert(!session!.started)
        try session!.start { _ in launches += 1 }
        expectFailure { try session!.start { _ in launches += 1 } }
        expectFailure { _ = try session!.select(second) }
        assert(launches == 1)
        session = nil
        assert(a.events.last == "end:" + first.path)
        let relaunched = GameDataSession(access: a, bookmarks: bookmarks)
        let restored = try relaunched.restore()
        assert(restored.root == first)
        a.corrupt = true
        expectFailure { _ = try GameDataSession(access: a, bookmarks: bookmarks).restore() }
        assert(bookmarks.data == original)
        let redirectedAccess = Access()
        redirectedAccess.coordinatedRoot = URL(fileURLWithPath: "/coordinated/data")
        var redirected: GameDataSession? = GameDataSession(access: redirectedAccess, bookmarks: Bookmarks())
        _ = try redirected!.select(first)
        redirected = nil
        assert(redirectedAccess.events.last == "end:" + first.path, "SCOPE_MUST_RELEASE_THE_ORIGINAL_GRANTED_URL")
        print("PASS: selection, persistence, failed replacement, permission revocation, disconnect/reconnect, launch failure, duplicate start and scope lifetime")

        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let identity = GameDataIdentity(titleID: "0100B8A026F14000", mainBuild: "b7f965b9d7227db8e29f04e84ea7331b", shaderChain: "test", shaderInputs: "input")
        let marker = "FFRS/Content/Paks/FFRS-Switch.ucas"
        let paths = ["romfs/" + marker, "msl/b-test/inputs.tsv"]
        for path in paths { try FileManager.default.createDirectory(at: root.appendingPathComponent(path).deletingLastPathComponent(), withIntermediateDirectories: true) }
        try Data("asset".utf8).write(to: root.appendingPathComponent(paths[0]))
        try Data("game\t\(identity.titleID)\ninputs\tinput\n".utf8).write(to: root.appendingPathComponent(paths[1]))
        let files = try paths.map { path in GameDataFile(path: path, size: Int64(try Data(contentsOf: root.appendingPathComponent(path)).count), sha256: String(repeating: "0", count: 64)) }
        func manifest(_ id: GameDataIdentity) throws { try JSONEncoder().encode(GameDataManifest(formatVersion: 1, identity: id, files: files)).write(to: root.appendingPathComponent("game-data.json")) }
        try manifest(identity)
        _ = try GameDataValidator.validate(root: root, expected: identity, marker: marker, full: true)
        let wrong = GameDataIdentity(titleID: "wrong", mainBuild: identity.mainBuild, shaderChain: "test", shaderInputs: "input")
        try manifest(wrong)
        expectFailure { _ = try GameDataValidator.validate(root: root, expected: identity, marker: marker, full: true) }
        try manifest(identity)
        try Data("short".utf8).write(to: root.appendingPathComponent(paths[1]))
        expectFailure { _ = try GameDataValidator.validate(root: root, expected: identity, marker: marker, full: true) }
        assert(!GameDataValidator.safePath("romfs/../../secret"))
        assert(!GameDataValidator.safePath("/romfs/a"))
        assert(!GameDataValidator.safePath("romfs\\a"))
        print("PASS: real directory validation, identity mismatch, truncated files and unsafe paths")
    }
}
