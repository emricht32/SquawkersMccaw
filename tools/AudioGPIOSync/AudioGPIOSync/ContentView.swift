//
//  ContentView.swift
//  AudioGPIOSync
//
//  Created by Jon Emrich on 6/28/26.
//
//  Root view, toolbar, and empty state.
//  Other parts live in:
//    Models.swift            – JSON config structs + BirdRuntime
//    PlayerViewModel.swift   – audio playback + GPIO state logic
//    TimelineViews.swift     – scrollable interval timeline
//    GPIOStatusViews.swift   – real-time GPIO pin cards
//    PlaybackControlsView.swift – transport controls
//

import SwiftUI
import AppKit

// MARK: - Root View

struct ContentView: View {
    @StateObject private var vm = PlayerViewModel()

    var body: some View {
        VStack(spacing: 0) {
            ToolbarBar(vm: vm)
            Divider()

            if vm.config != nil {
                VStack(spacing: 0) {
                    SongTimelineView(vm: vm)
                        .frame(minHeight: 160)
                        .frame(maxHeight: .infinity)
                    Divider()
                    GPIOStatusPanel(vm: vm)
                        .frame(height: 170)
                    Divider()
                    PlaybackControlsView(vm: vm)
                        .frame(height: 60)
                }
            } else {
                EmptyStateView(vm: vm)
            }
        }
        .frame(minWidth: 920, minHeight: 680)
        .alert("Error", isPresented: Binding(
            get: { vm.loadError != nil },
            set: { if !$0 { vm.loadError = nil } }
        )) {
            Button("OK") { vm.loadError = nil }
        } message: {
            Text(vm.loadError ?? "")
        }
    }
}

// MARK: - Toolbar

struct ToolbarBar: View {
    @ObservedObject var vm: PlayerViewModel

    var body: some View {
        HStack(spacing: 10) {
            Button("Load JSON") { vm.openJSONPanel() }
                .buttonStyle(.bordered)

            if let songs = vm.config?.songs, songs.count > 1 {
                Divider().frame(height: 20)
                Picker("Song:", selection: Binding(
                    get: { vm.selectedSong?.id ?? "" },
                    set: { id in
                        if let s = songs.first(where: { $0.id == id }) { vm.selectSong(s) }
                    }
                )) {
                    ForEach(songs) { Text($0.displayName).tag($0.id) }
                }
                .frame(maxWidth: 280)
            }

            Spacer()

            if let url = vm.jsonURL {
                HStack(spacing: 4) {
                    if vm.isDirty {
                        Image(systemName: "circle.fill")
                            .font(.system(size: 7))
                            .foregroundStyle(.orange)
                    }
                    Label(url.lastPathComponent, systemImage: "doc.text")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            if !vm.audioFileName.isEmpty {
                Label(vm.audioFileName, systemImage: "music.note")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Divider().frame(height: 20)

            Button(action: vm.undo) {
                Image(systemName: "arrow.uturn.backward")
            }
            .buttonStyle(.plain)
            .foregroundStyle(vm.canUndo ? .primary : .secondary)
            .disabled(!vm.canUndo)
            .help("Undo (⌘Z)")
            .keyboardShortcut("z", modifiers: .command)

            Button(action: vm.redo) {
                Image(systemName: "arrow.uturn.forward")
            }
            .buttonStyle(.plain)
            .foregroundStyle(vm.canRedo ? .primary : .secondary)
            .disabled(!vm.canRedo)
            .help("Redo (⌘⇧Z)")
            .keyboardShortcut("z", modifiers: [.command, .shift])

            Button("Save") { vm.saveJSON() }
                .buttonStyle(.bordered)
                .disabled(!vm.isDirty)
                .keyboardShortcut("s", modifiers: .command)

            Button("Cancel") { vm.cancelEdits() }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .disabled(!vm.isDirty)

            Button("Save As…") { vm.saveJSONAs() }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .disabled(vm.config == nil)

            if vm.isNonMasterConfig {
                Button("Save to Master") { vm.saveToMasterConfig() }
                    .buttonStyle(.bordered)
                    .help("Merge this song into config_multi_song_with_triggers.json")
            }

            Divider().frame(height: 20)

            HStack(spacing: 4) {
                Image(systemName: "minus.magnifyingglass").foregroundStyle(.secondary)
                Slider(value: $vm.pixelsPerSecond, in: 4...120, step: 4)
                    .frame(width: 110)
                Image(systemName: "plus.magnifyingglass").foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }
}

// MARK: - Empty State

struct EmptyStateView: View {
    @ObservedObject var vm: PlayerViewModel

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "bird.fill")
                .font(.system(size: 72))
                .foregroundStyle(.secondary)
            Text("AudioGPIOSync")
                .font(.largeTitle.bold())
            Text("Load a SquawkersMccaw JSON config to visualize GPIO trigger timings along the audio timeline.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)
            HStack(spacing: 12) {
                Button("Load JSON Config") { vm.openJSONPanel() }
                    .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Preview

#Preview {
    ContentView()
}


