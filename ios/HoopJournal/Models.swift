import Foundation

struct Shot: Codable, Identifiable {
    var id = UUID().uuidString
    var start: Double
    var release: Double
    var end: Double
    var outcome: String = "unknown"
    var reviewed: Bool = false
    var note: String = ""
    var label: String { !reviewed ? "待核对" : outcome == "made" ? "命中" : outcome == "missed" ? "未命中" : "无法判断" }
}

struct Stats: Codable {
    let attempts: Int
    let made: Int
    let pending: Int
    let percentage: Double?
    var rate: String { percentage.map { String(format: "%.1f%%", $0) } ?? "—" }
}

struct Training: Codable, Identifiable {
    let id: String
    let title: String
    let date: String
    let player: String
    let duration: Double
    var shots: [Shot]
    let revision: Int
    let turns: Int
    let busy: Bool
    let status: String
    let error: String
    let stats: Stats
    let report: String
    let aiAvailable: Bool
    let previewReady: Bool
    let highlightReady: Bool
    let highlightStale: Bool
}

func timestamp(_ value: Double) -> String {
    guard value.isFinite else { return "00:00" }
    return String(format: "%02d:%02d", Int(value)/60, Int(value)%60)
}
