//
//  Models.swift
//  AudioGPIOSync
//
//  Data models that mirror the SquawkersMccaw JSON config schema.
//

import Foundation

// MARK: - JSON Config Models

struct BirdConfig: Codable, Identifiable {
    var id: String { name }
    let name: String
    let beak: Int?
    let body: Int?
    let light: Int?
    let lights: [Int]?
    let on_time: Double?

    var lightPins: [Int] {
        if let l = lights, !l.isEmpty { return l }
        if let l = light { return [l] }
        return []
    }
}

struct Individual: Codable {
    let name: String
    let _name: String?
    let singing: [[Double]]
    let dancing: [[Double]]
}

struct SongConfig: Codable, Identifiable {
    var id: String { name }
    let name: String
    let display_name: String?
    let audio_dir: String?
    let individuals: [Individual]?
    let all_singing: [[Double]]?
    let all_dancing: [[Double]]?
    let triggers: [String]?

    var displayName: String { display_name ?? name }
}

struct AppConfig: Codable {
    let power: Int?
    let birds: [BirdConfig]?
    let songs: [SongConfig]?
}

// MARK: - Bird Runtime State

struct BirdRuntime: Identifiable {
    let id = UUID()
    let config: BirdConfig
    var displayName: String   // may include "(alias)" from Individual._name
    var isSinging: Bool = false
    var isDancing: Bool = false

    // beak = singing only; body+light = sing or dance
    var beakActive: Bool { isSinging }
    var bodyActive: Bool { isSinging || isDancing }
    var lightActive: Bool { isSinging || isDancing }

    // Merged intervals (individual + all_singing/all_dancing) – used for playback
    var singingIntervals: [ClosedRange<Double>] = []
    var dancingIntervals: [ClosedRange<Double>] = []

    // Individual-only intervals – used for display/editing per-bird row
    var individualSingingIntervals: [ClosedRange<Double>] = []
    var individualDancingIntervals: [ClosedRange<Double>] = []
}

// MARK: - Editing Types

enum IntervalType: Equatable { case singing, dancing }

enum RowKey: Hashable {
    case allBirds
    case bird(String)
}

struct SelectedInterval: Equatable {
    var rowKey: RowKey
    var type: IntervalType
    var index: Int
}
