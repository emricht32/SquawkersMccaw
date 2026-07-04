//
//  GPIOStatusViews.swift
//  AudioGPIOSync
//
//  The GPIO status panel: per-bird cards with live pin indicators.
//

import SwiftUI
import AppKit

// MARK: - GPIO Status Panel

struct GPIOStatusPanel: View {
    @ObservedObject var vm: PlayerViewModel

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: 12) {
                LegendCard()
                ForEach(vm.birdRuntimes) { GPIOStatusCard(bird: $0) }
            }
            .padding(12)
        }
        .background(Color(NSColor.windowBackgroundColor))
        .clipped()
    }
}

// MARK: - Legend Card

struct LegendCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("GPIO Legend")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 5) {
                legendRow(.orange, "Beak",  "singing only")
                legendRow(.yellow, "Body",  "sing + dance")
                legendRow(.cyan,   "Light", "sing + dance")
            }
            HStack(spacing: 4) {
                RoundedRectangle(cornerRadius: 2).fill(Color.orange.opacity(0.8)).frame(width: 18, height: 8)
                Text("Top = singing").font(.system(size: 8)).foregroundStyle(.secondary)
            }
            HStack(spacing: 4) {
                RoundedRectangle(cornerRadius: 2).fill(Color.teal.opacity(0.65)).frame(width: 18, height: 8)
                Text("Bottom = dancing").font(.system(size: 8)).foregroundStyle(.secondary)
            }
        }
        .padding(10)
        .frame(width: 130)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color(NSColor.secondarySystemFill)))
    }

    private func legendRow(_ color: Color, _ pin: String, _ when: String) -> some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 0) {
                Text(pin).font(.caption2.bold())
                Text(when).font(.system(size: 8)).foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Bird Status Card

struct GPIOStatusCard: View {
    let bird: BirdRuntime
    private var isActive: Bool { bird.isSinging || bird.isDancing }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(bird.displayName).font(.system(size: 13, weight: .semibold))
                Spacer()
                statusBadge
            }
            HStack(alignment: .top, spacing: 10) {
                if let p = bird.config.beak { PinIndicator(label: "Beak",  pin: p, active: bird.beakActive,  color: .orange) }
                if let p = bird.config.body { PinIndicator(label: "Body",  pin: p, active: bird.bodyActive,  color: .yellow) }
                ForEach(bird.config.lightPins, id: \.self) { p in
                    PinIndicator(label: "Light", pin: p, active: bird.lightActive, color: .cyan)
                }
            }
        }
        .padding(10)
        .frame(minWidth: 150)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(isActive ? Color.accentColor.opacity(0.12) : Color(NSColor.secondarySystemFill))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(bird.isSinging ? Color.orange.opacity(0.7) : Color.clear, lineWidth: 1.5)
        )
        .animation(.easeInOut(duration: 0.08), value: isActive)
    }

    private var statusBadge: some View {
        Text(bird.isSinging ? "SING" : bird.isDancing ? "DANCE" : "IDLE")
            .font(.system(size: 9, weight: .bold, design: .monospaced))
            .foregroundStyle(bird.isSinging ? Color.orange : bird.isDancing ? Color.teal : Color.secondary)
            .padding(.horizontal, 5).padding(.vertical, 2)
            .background(
                RoundedRectangle(cornerRadius: 4)
                    .fill(bird.isSinging ? Color.orange.opacity(0.15) : Color.clear)
            )
    }
}

// MARK: - Pin Indicator

struct PinIndicator: View {
    let label: String
    let pin: Int
    let active: Bool
    let color: Color

    var body: some View {
        VStack(spacing: 3) {
            ZStack {
                if active {
                    Circle()
                        .fill(color.opacity(0.25))
                        .frame(width: 24, height: 24)
                }
                Circle()
                    .fill(active ? color : Color.gray.opacity(0.25))
                    .frame(width: 14, height: 14)
            }
            .shadow(color: active ? color.opacity(0.6) : .clear, radius: 4)
            .animation(.easeInOut(duration: 0.08), value: active)

            Text(label).font(.system(size: 9, weight: .medium)).foregroundStyle(active ? .primary : .secondary)
            Text("GPIO\(pin)").font(.system(size: 8, design: .monospaced)).foregroundStyle(.secondary)
        }
    }
}
