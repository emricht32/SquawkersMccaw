//
//  PlaybackControlsView.swift
//  AudioGPIOSync
//
//  Transport controls: stop, play/pause, seek slider, and time display.
//

import SwiftUI

struct PlaybackControlsView: View {
    @ObservedObject var vm: PlayerViewModel

    var body: some View {
        HStack(spacing: 14) {
            Button(action: vm.stop) {
                Image(systemName: "stop.fill").font(.system(size: 14))
            }
            .buttonStyle(.plain)
            .foregroundStyle(vm.duration > 0 ? .primary : .secondary)
            .disabled(vm.duration == 0)

            Button(action: vm.togglePlayPause) {
                Image(systemName: vm.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                    .font(.system(size: 30))
            }
            .buttonStyle(.plain)
            .foregroundStyle(vm.duration > 0 ? Color.accentColor : Color.secondary)
            .disabled(vm.duration == 0)
            .keyboardShortcut(.space, modifiers: [])

            Text(formatTime(vm.currentTime))
                .font(.system(size: 13, design: .monospaced))
                .frame(width: 52)

            Slider(
                value: Binding(get: { vm.currentTime }, set: { vm.seek(to: $0) }),
                in: 0...max(vm.duration, 1)
            )

            Text(formatTime(vm.duration))
                .font(.system(size: 13, design: .monospaced))
                .foregroundStyle(.secondary)
                .frame(width: 52)
        }
        .padding(.horizontal, 16)
    }

    private func formatTime(_ t: Double) -> String {
        String(format: "%d:%02d", Int(t) / 60, Int(t) % 60)
    }
}
