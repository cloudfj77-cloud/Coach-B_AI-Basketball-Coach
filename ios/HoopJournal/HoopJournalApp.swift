import SwiftUI

@main struct HoopJournalApp: App {
    @StateObject private var journal = Journal()
    var body: some Scene {
        WindowGroup {
            HomeView().environmentObject(journal).tint(.orange).preferredColorScheme(.dark)
        }
    }
}
