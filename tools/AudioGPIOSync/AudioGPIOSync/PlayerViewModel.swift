//
//  PlayerViewModel.swift
//  AudioGPIOSync
//
//  Drives audio playback and computes which bird GPIO pins are active
//  at any given moment in the song.
//

import AVFoundation
import SwiftUI
import UniformTypeIdentifiers
import AppKit
import Combine

@MainActor
class PlayerViewModel: ObservableObject {
    @Published var config: AppConfig?
    @Published var selectedSong: SongConfig?
    @Published var jsonURL: URL?
    @Published var audioURL: URL?
    @Published var currentTime: Double = 0
    @Published var duration: Double = 0
    @Published var isPlaying: Bool = false
    @Published var pixelsPerSecond: Double = 20.0
    @Published var birdRuntimes: [BirdRuntime] = []
    @Published var allSingingIntervals: [ClosedRange<Double>] = []
    @Published var allDancingIntervals: [ClosedRange<Double>] = []
    @Published var loadError: String?
    @Published var audioFileName: String = ""
    @Published var selectedInterval: SelectedInterval? = nil
    @Published var isDirty: Bool = false
    @Published var canUndo: Bool = false
    @Published var canRedo: Bool = false
    @Published var autoScrollEnabled: Bool = false

    /// True when the loaded JSON is NOT the master config file.
    var isNonMasterConfig: Bool {
        guard let name = jsonURL?.lastPathComponent else { return false }
        return name != "config_multi_song_with_triggers.json"
    }

    private var audioPlayer: AVAudioPlayer?
    private var displayTimer: Timer?

    // MARK: - Undo / Redo

    private struct EditSnapshot {
        let birdRuntimes: [BirdRuntime]
        let allSinging: [ClosedRange<Double>]
        let allDancing: [ClosedRange<Double>]
    }

    private var undoStack: [EditSnapshot] = []
    private var redoStack: [EditSnapshot] = []

    private func captureSnapshot() -> EditSnapshot {
        EditSnapshot(birdRuntimes: birdRuntimes,
                     allSinging: allSingingIntervals,
                     allDancing: allDancingIntervals)
    }

    private func pushUndo() {
        undoStack.append(captureSnapshot())
        if undoStack.count > 100 { undoStack.removeFirst() }
        redoStack.removeAll()
        updateUndoRedoState()
    }

    private func updateUndoRedoState() {
        canUndo = !undoStack.isEmpty
        canRedo = !redoStack.isEmpty
    }

    func undo() {
        guard let snap = undoStack.last else { return }
        redoStack.append(captureSnapshot())
        undoStack.removeLast()
        applySnapshot(snap)
        updateUndoRedoState()
    }

    func redo() {
        guard let snap = redoStack.last else { return }
        undoStack.append(captureSnapshot())
        redoStack.removeLast()
        applySnapshot(snap)
        updateUndoRedoState()
    }

    private func applySnapshot(_ snap: EditSnapshot) {
        birdRuntimes = snap.birdRuntimes
        allSingingIntervals = snap.allSinging
        allDancingIntervals = snap.allDancing
        isDirty = true
    }

    func cancelEdits() {
        guard let url = jsonURL else { return }
        loadJSON(url: url)
    }

    // MARK: - Open Panels

    func openJSONPanel() {
        let panel = NSOpenPanel()
        panel.title = "Choose a SquawkersMccaw JSON config"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.json]
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url else { return }
            self?.loadJSON(url: url)
        }
    }

    // MARK: - Load JSON

    func loadJSON(url: URL) {
        do {
            let data = try Data(contentsOf: url)
            let decoded = try JSONDecoder().decode(AppConfig.self, from: data)
            config = decoded
            jsonURL = url
            loadError = nil
            if let first = decoded.songs?.first {
                selectSong(first, relativeTo: url)
            }
        } catch {
            loadError = "JSON parse error: \(error.localizedDescription)"
        }
    }

    func selectSong(_ song: SongConfig, relativeTo base: URL? = nil) {
        selectedSong = song
        buildBirdRuntimes(for: song)
        let baseURL = base ?? jsonURL
        if let baseURL, let audioDir = song.audio_dir {
            tryAutoLoadAudio(audioDir: audioDir, relativeTo: baseURL)
        }
    }

    private func tryAutoLoadAudio(audioDir: String, relativeTo jsonURL: URL) {
        let dir = jsonURL.deletingLastPathComponent()
        let candidates = [
            dir.appendingPathComponent(audioDir),
            dir.deletingLastPathComponent().appendingPathComponent(audioDir),
            dir.appendingPathComponent("music").appendingPathComponent(audioDir)
        ]
        for candidate in candidates {
            if let mp3 = firstMP3(in: candidate) {
                loadAudio(url: mp3)
                return
            }
        }
    }

    private func firstMP3(in dir: URL) -> URL? {
        (try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil))?
            .first { $0.pathExtension.lowercased() == "mp3" }
    }

    // MARK: - Build Runtimes

    private func buildBirdRuntimes(for song: SongConfig) {
        let allSing  = song.all_singing?.compactMap(makeRange) ?? []
        let allDance = song.all_dancing?.compactMap(makeRange) ?? []
        allSingingIntervals = allSing
        allDancingIntervals = allDance
        isDirty = false
        selectedInterval = nil
        undoStack.removeAll()
        redoStack.removeAll()
        updateUndoRedoState()

        guard let birds = config?.birds, !birds.isEmpty else {
            birdRuntimes = []
            return
        }

        birdRuntimes = birds.map { cfg in
            let individual = song.individuals?.first(where: { $0.name == cfg.name })
            let alias = individual?._name
            var rt = BirdRuntime(config: cfg,
                                 displayName: alias.map { "\(cfg.name) (\($0))" } ?? cfg.name)
            let indSing  = individual?.singing.compactMap(makeRange) ?? []
            let indDance = individual?.dancing.compactMap(makeRange) ?? []
            rt.individualSingingIntervals = indSing
            rt.individualDancingIntervals = indDance
            rt.singingIntervals = indSing + allSing
            rt.dancingIntervals  = indDance + allDance
            return rt
        }
    }

    private func makeRange(_ arr: [Double]) -> ClosedRange<Double>? {
        guard arr.count >= 2, arr[0] <= arr[1] else { return nil }
        return arr[0]...arr[1]
    }

    // MARK: - Load Audio

    func loadAudio(url: URL) {
        stop()
        do {
            audioPlayer = try AVAudioPlayer(contentsOf: url)
            audioPlayer?.prepareToPlay()
            duration = audioPlayer?.duration ?? 0
            audioURL = url
            audioFileName = url.lastPathComponent
            loadError = nil
        } catch {
            loadError = "Audio error: \(error.localizedDescription)"
        }
    }

    // MARK: - Playback

    func play() {
        guard let player = audioPlayer else { return }
        player.play()
        isPlaying = true
        autoScrollEnabled = true
        startTimer()
    }

    func pause() {
        audioPlayer?.pause()
        isPlaying = false
        stopTimer()
    }

    func stop() {
        audioPlayer?.stop()
        audioPlayer?.currentTime = 0
        isPlaying = false
        currentTime = 0
        stopTimer()
        updateBirdStates()
    }

    func togglePlayPause() {
        isPlaying ? pause() : play()
    }

    func seek(to time: Double) {
        let t = max(0, min(time, duration))
        audioPlayer?.currentTime = t
        currentTime = t
        updateBirdStates()
    }

    func userDidManuallyScroll() {
        autoScrollEnabled = false
    }

    // MARK: - Timer

    private func startTimer() {
        stopTimer()
        displayTimer = Timer.scheduledTimer(withTimeInterval: 0.04, repeats: true) { [weak self] _ in
            guard let self else { return }
            if let player = self.audioPlayer {
                self.currentTime = player.currentTime
                if !player.isPlaying && self.isPlaying {
                    self.isPlaying = false
                    self.stopTimer()
                }
            }
            self.updateBirdStates()
        }
        RunLoop.main.add(displayTimer!, forMode: .common)
    }

    private func stopTimer() {
        displayTimer?.invalidate()
        displayTimer = nil
    }

    func updateBirdStates() {
        let t = currentTime
        for i in birdRuntimes.indices {
            birdRuntimes[i].isSinging = birdRuntimes[i].singingIntervals.contains { $0.contains(t) }
            birdRuntimes[i].isDancing = birdRuntimes[i].dancingIntervals.contains { $0.contains(t) }
        }
    }

    var timelineWidth: Double { duration * pixelsPerSecond }

    // MARK: - Interval Editing

    /// Returns the editable intervals for a row: individual-only per bird, or all_singing/all_dancing for .allBirds.
    func displayIntervals(for rowKey: RowKey, type: IntervalType) -> [ClosedRange<Double>] {
        switch (rowKey, type) {
        case (.allBirds, .singing):  return allSingingIntervals
        case (.allBirds, .dancing):  return allDancingIntervals
        case (.bird(let name), .singing):
            return birdRuntimes.first(where: { $0.config.name == name })?.individualSingingIntervals ?? []
        case (.bird(let name), .dancing):
            return birdRuntimes.first(where: { $0.config.name == name })?.individualDancingIntervals ?? []
        }
    }

    // Apply an array to the right slot and keep merged playback arrays in sync.
    private func applyDisplayIntervals(_ arr: [ClosedRange<Double>], rowKey: RowKey, type: IntervalType) {
        switch (rowKey, type) {
        case (.allBirds, .singing):
            allSingingIntervals = arr
            for i in birdRuntimes.indices {
                birdRuntimes[i].singingIntervals = birdRuntimes[i].individualSingingIntervals + arr
            }
        case (.allBirds, .dancing):
            allDancingIntervals = arr
            for i in birdRuntimes.indices {
                birdRuntimes[i].dancingIntervals = birdRuntimes[i].individualDancingIntervals + arr
            }
        case (.bird(let name), .singing):
            guard let i = birdRuntimes.firstIndex(where: { $0.config.name == name }) else { return }
            birdRuntimes[i].individualSingingIntervals = arr
            birdRuntimes[i].singingIntervals = arr + allSingingIntervals
        case (.bird(let name), .dancing):
            guard let i = birdRuntimes.firstIndex(where: { $0.config.name == name }) else { return }
            birdRuntimes[i].individualDancingIntervals = arr
            birdRuntimes[i].dancingIntervals = arr + allDancingIntervals
        }
    }

    func addInterval(_ range: ClosedRange<Double>, rowKey: RowKey, type: IntervalType) {
        pushUndo()
        var arr = displayIntervals(for: rowKey, type: type)
        arr.append(range)
        arr.sort { $0.lowerBound < $1.lowerBound }
        applyDisplayIntervals(arr, rowKey: rowKey, type: type)
        isDirty = true
    }

    func removeInterval(at index: Int, rowKey: RowKey, type: IntervalType) {
        pushUndo()
        var arr = displayIntervals(for: rowKey, type: type)
        guard arr.indices.contains(index) else { return }
        arr.remove(at: index)
        applyDisplayIntervals(arr, rowKey: rowKey, type: type)
        if let sel = selectedInterval, sel.rowKey == rowKey, sel.type == type, sel.index == index {
            selectedInterval = nil
        }
        isDirty = true
    }

    /// Called once at drag start so one continuous drag = one undo step.
    func beginIntervalUpdate() { pushUndo() }

    /// In-place update without sorting or pushing undo – called repeatedly during drag.
    func updateInterval(at index: Int, rowKey: RowKey, type: IntervalType, newRange: ClosedRange<Double>) {
        var arr = displayIntervals(for: rowKey, type: type)
        guard arr.indices.contains(index) else { return }
        arr[index] = newRange
        applyDisplayIntervals(arr, rowKey: rowKey, type: type)
        isDirty = true
    }

    // MARK: - Save / Export

    func saveJSON() {
        guard let url = jsonURL else { saveJSONAs(); return }
        guard let data = buildExportData(merging: true) else { return }
        do { try data.write(to: url); isDirty = false }
        catch { loadError = "Save failed: \(error.localizedDescription)" }
    }

    func saveJSONAs() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = jsonURL?.lastPathComponent ?? "config.json"
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url,
                  let data = self?.buildExportData(merging: true) else { return }
            do { try data.write(to: url); self?.jsonURL = url; self?.isDirty = false }
            catch { self?.loadError = "Save failed: \(error.localizedDescription)" }
        }
    }

    /// Save the current config's data into config_multi_song_with_triggers.json.
    /// Replaces any song with the same name; appends if not present.
    func saveToMasterConfig() {
        // Locate the master config next to the loaded JSON, or one directory up (project root).
        let candidates: [URL] = {
            guard let base = jsonURL?.deletingLastPathComponent() else { return [] }
            let name = "config_multi_song_with_triggers.json"
            return [
                base.appendingPathComponent(name),
                base.deletingLastPathComponent().appendingPathComponent(name)
            ]
        }()
        guard let masterURL = candidates.first(where: { FileManager.default.fileExists(atPath: $0.path) }) else {
            loadError = "config_multi_song_with_triggers.json not found near \(jsonURL?.lastPathComponent ?? "")."
            return
        }
        // Decode master config.
        guard let masterData = try? Data(contentsOf: masterURL),
              var masterConfig = try? JSONDecoder().decode(AppConfig.self, from: masterData) else {
            loadError = "Could not read master config."
            return
        }
        // Build the updated song dict from current edits.
        guard let exportData = buildExportData(merging: true),
              let exportObj = (try? JSONSerialization.jsonObject(with: exportData)) as? [String: Any],
              let exportSongs = exportObj["songs"] as? [[String: Any]],
              let exportSong = exportSongs.first,
              let currentSong = selectedSong else {
            loadError = "Could not build export data."
            return
        }
        // Rebuild master songs array, replacing matching song or appending.
        var masterSongs: [[String: Any]] = (masterConfig.songs ?? []).compactMap { s in
            guard let d = try? JSONEncoder().encode(s) else { return nil }
            return (try? JSONSerialization.jsonObject(with: d)) as? [String: Any]
        }
        if let idx = masterSongs.firstIndex(where: { ($0["name"] as? String) == currentSong.name }) {
            masterSongs[idx] = exportSong
        } else {
            masterSongs.append(exportSong)
        }
        var masterDict: [String: Any] = ["songs": masterSongs]
        if let power = masterConfig.power { masterDict["power"] = power }
        if let birds = masterConfig.birds {
            masterDict["birds"] = birds.map { b -> [String: Any] in
                var d: [String: Any] = ["name": b.name]
                if let v = b.beak    { d["beak"]    = v }
                if let v = b.body    { d["body"]    = v }
                if let v = b.light   { d["light"]   = v }
                if let v = b.lights, !v.isEmpty { d["lights"] = v }
                if let v = b.on_time { d["on_time"] = v }
                return d
            }
        }
        guard let outData = try? JSONSerialization.data(withJSONObject: masterDict,
                                                        options: [.prettyPrinted, .sortedKeys]) else {
            loadError = "Serialization failed."
            return
        }
        do {
            try outData.write(to: masterURL)
        } catch {
            loadError = "Save to master failed: \(error.localizedDescription)"
        }
    }

    /// Merge adjacent intervals whose gap is < threshold seconds.
    private func mergeClose(_ arr: [ClosedRange<Double>], threshold: Double = 0.3) -> [ClosedRange<Double>] {
        let sorted = arr.sorted { $0.lowerBound < $1.lowerBound }
        var result: [ClosedRange<Double>] = []
        for interval in sorted {
            if let last = result.last, interval.lowerBound - last.upperBound < threshold {
                result[result.count - 1] = last.lowerBound...max(last.upperBound, interval.upperBound)
            } else {
                result.append(interval)
            }
        }
        return result
    }

    private func buildExportData(merging: Bool) -> Data? {
        guard let config = self.config,
              let song = selectedSong,
              let songs = config.songs,
              let songIdx = songs.firstIndex(where: { $0.id == song.id }) else { return nil }

        let updatedIndividuals: [[String: Any]] = birdRuntimes.map { rt in
            let sing  = merging ? mergeClose(rt.individualSingingIntervals) : rt.individualSingingIntervals
            let dance = merging ? mergeClose(rt.individualDancingIntervals) : rt.individualDancingIntervals
            return ["name": rt.config.name,
                    "singing": sing.map  { [$0.lowerBound, $0.upperBound] },
                    "dancing": dance.map { [$0.lowerBound, $0.upperBound] }
            ] as [String: Any]
        }
        let allSing  = merging ? mergeClose(allSingingIntervals) : allSingingIntervals
        let allDance = merging ? mergeClose(allDancingIntervals) : allDancingIntervals

        var songDict: [String: Any] = [
            "name": song.name,
            "audio_dir": song.audio_dir ?? "",
            "individuals": updatedIndividuals,
            "all_singing": allSing.map  { [$0.lowerBound, $0.upperBound] },
            "all_dancing":  allDance.map { [$0.lowerBound, $0.upperBound] },
            "triggers": song.triggers ?? []
        ]
        if let dn = song.display_name { songDict["display_name"] = dn }

        var songsArray: [[String: Any]] = []
        for (i, s) in songs.enumerated() {
            if i == songIdx {
                songsArray.append(songDict)
            } else if let d = try? JSONEncoder().encode(s),
                      let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                songsArray.append(obj)
            }
        }

        var configDict: [String: Any] = ["songs": songsArray]
        if let power = config.power { configDict["power"] = power }
        if let birds = config.birds {
            configDict["birds"] = birds.map { b -> [String: Any] in
                var d: [String: Any] = ["name": b.name]
                if let v = b.beak    { d["beak"]    = v }
                if let v = b.body    { d["body"]    = v }
                if let v = b.light   { d["light"]   = v }
                if let v = b.lights, !v.isEmpty { d["lights"] = v }
                if let v = b.on_time { d["on_time"] = v }
                return d
            }
        }
        return try? JSONSerialization.data(withJSONObject: configDict, options: [.prettyPrinted, .sortedKeys])
    }
}
