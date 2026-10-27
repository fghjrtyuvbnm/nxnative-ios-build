import XCTest

@MainActor final class FolderUITests: XCTestCase {
    func testFolderSelectionIsRequiredAndCancellationKeepsPlayDisabled() throws {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launch()
        let choose = app.buttons["Choose data folder"]
        XCTAssertTrue(choose.waitForExistence(timeout: 15), "EXTERNAL_FOLDER_PICKER_MISSING")
        XCTAssertFalse(app.buttons["Play"].isEnabled)
        choose.tap()
        let cancel = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(cancel.waitForExistence(timeout: 15), "NATIVE_DIRECTORY_PICKER_NOT_PRESENTED")
        cancel.tap()
        XCTAssertTrue(choose.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["Play"].isEnabled)
        let shot = XCTAttachment(screenshot: app.screenshot()); shot.lifetime = .keepAlways; add(shot)
    }
}
