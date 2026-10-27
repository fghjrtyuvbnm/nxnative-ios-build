// Test-only app: the production Swift launcher, without the native game or a GPU renderer.
import UIKit

private func finished() {}
final class HarnessRoot: UIViewController {
    private var shown = false
    override func viewDidLoad() {
        super.viewDidLoad(); view.backgroundColor = .black
        let label = UILabel(frame: view.bounds)
        label.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        label.text = "Launcher unavailable"; label.textColor = .white; label.textAlignment = .center
        view.addSubview(label)
    }
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        guard !shown else { return }; shown = true
        _ = dmShowLauncher(Unmanaged.passUnretained(self).toOpaque(), finished)
    }
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .landscape }
}
@main final class HarnessApp: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = HarnessRoot(); window?.makeKeyAndVisible()
        return true
    }
}
