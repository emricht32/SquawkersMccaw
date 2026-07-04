//
//  TimelineViews.swift
//  AudioGPIOSync
//
//  The scrollable song timeline: ruler, per-bird interval rows, and playhead.
//

import SwiftUI
import AppKit

// MARK: - Song Timeline

struct SongTimelineView: View {
    @ObservedObject var vm: PlayerViewModel

    private let labelWidth: CGFloat = 140
    private let rowHeight:  CGFloat = 48
    private let rulerHeight: CGFloat = 30

    private var hasAllBirdsRow: Bool {
        !vm.allSingingIntervals.isEmpty || !vm.allDancingIntervals.isEmpty
    }

    var body: some View {
        GeometryReader { outer in
            // Available width for the scroll area (total minus label column and divider)
            let viewportWidth = max(outer.size.width - labelWidth - 1, 0)
            // Content is at least as wide as the viewport so it always fills to the right edge
            let trackWidth = max(CGFloat(vm.timelineWidth), viewportWidth)

            HStack(spacing: 0) {
                // Fixed labels column (does not scroll horizontally)
                VStack(spacing: 0) {
                    Color.clear.frame(height: rulerHeight)
                    Divider()
                    if hasAllBirdsRow {
                        allBirdsLabel.frame(height: rowHeight)
                        Divider()
                    }
                    ForEach(Array(vm.birdRuntimes.enumerated()), id: \.element.id) { _, bird in
                        birdLabel(bird).frame(height: rowHeight)
                        Divider()
                    }
                    Spacer()
                }
                .frame(width: labelWidth)
                .background(Color(NSColor.windowBackgroundColor))

                Divider()

                // Horizontally scrollable timeline content
                ScrollView(.horizontal, showsIndicators: true) {
                    ZStack(alignment: .topLeading) {
                        VStack(spacing: 0) {
                            TimeRulerView(vm: vm, width: trackWidth)
                                .overlay(
                                    MouseSeekOverlay(
                                        pixelsPerSecond: vm.pixelsPerSecond,
                                        duration: vm.duration
                                    ) { t in vm.seek(to: t) }
                                )
                                .frame(width: trackWidth, height: rulerHeight)
                            Divider()

                            if hasAllBirdsRow {
                                IntervalRowView(rowKey: .allBirds, vm: vm)
                                    .frame(width: trackWidth, height: rowHeight)
                                Divider()
                            }

                            ForEach(Array(vm.birdRuntimes.enumerated()), id: \.element.id) { _, bird in
                                IntervalRowView(rowKey: .bird(bird.config.name), vm: vm)
                                    .frame(width: trackWidth, height: rowHeight)
                                Divider()
                            }
                            Spacer()
                        }

                        // Playhead overlay
                        if vm.duration > 0 {
                            GeometryReader { geo in
                                let x = CGFloat(vm.currentTime * vm.pixelsPerSecond)
                                ZStack(alignment: .topLeading) {
                                    Rectangle()
                                        .fill(Color.red.opacity(0.9))
                                        .frame(width: 1.5, height: geo.size.height)
                                        .offset(x: x - 0.75)
                                    Triangle()
                                        .fill(Color.red)
                                        .frame(width: 10, height: 9)
                                        .offset(x: x - 5, y: rulerHeight - 10)
                                }
                                .allowsHitTesting(false)
                            }
                        }

                        // Auto-scroll driver: zero-size view that finds the NSScrollView
                        TimelineAutoScroller(vm: vm, viewportWidth: viewportWidth)
                            .frame(width: 0, height: 0)
                    }
                    .frame(width: trackWidth)
                }
                .background(Color(NSColor.underPageBackgroundColor))
                .frame(maxWidth: .infinity)
            }
            .background(Color(NSColor.controlBackgroundColor))
        }
    }

    // MARK: - Labels

    private var allBirdsLabel: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text("All Birds")
                .font(.system(size: 11, weight: .semibold))
            HStack(spacing: 5) {
                legendChip(.orange, "Sing")
                legendChip(.teal,   "Dance")
            }
        }
        .padding(.horizontal, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func birdLabel(_ bird: BirdRuntime) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 5) {
                Circle()
                    .fill(
                        bird.isSinging ? Color.orange :
                        bird.isDancing ? Color.teal   :
                        Color.gray.opacity(0.4)
                    )
                    .frame(width: 8, height: 8)
                    .animation(.easeInOut(duration: 0.08), value: bird.isSinging || bird.isDancing)
                Text(bird.displayName)
                    .font(.system(size: 12, weight: .semibold))
            }
            HStack(spacing: 3) {
                if let p = bird.config.beak { pinTag("B\(p)",  active: bird.beakActive,  color: .orange) }
                if let p = bird.config.body { pinTag("M\(p)",  active: bird.bodyActive,  color: .yellow) }
                ForEach(bird.config.lightPins, id: \.self) { p in
                    pinTag("L\(p)", active: bird.lightActive, color: .cyan)
                }
            }
        }
        .padding(.horizontal, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func legendChip(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 2) {
            RoundedRectangle(cornerRadius: 2).fill(color.opacity(0.8)).frame(width: 10, height: 7)
            Text(label).font(.system(size: 9)).foregroundStyle(.secondary)
        }
    }

    private func pinTag(_ text: String, active: Bool, color: Color) -> some View {
        Text(text)
            .font(.system(size: 8, design: .monospaced))
            .foregroundStyle(active ? color : .secondary)
            .padding(.horizontal, 3).padding(.vertical, 1)
            .background(RoundedRectangle(cornerRadius: 3).fill(active ? color.opacity(0.18) : Color.clear))
    }
}

// MARK: - Triangle Shape

struct Triangle: Shape {
    func path(in rect: CGRect) -> Path {
        Path { p in
            p.move(to: CGPoint(x: rect.midX, y: rect.maxY))
            p.addLine(to: CGPoint(x: rect.minX, y: rect.minY))
            p.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
            p.closeSubpath()
        }
    }
}

// MARK: - Time Ruler

struct TimeRulerView: View {
    @ObservedObject var vm: PlayerViewModel
    let width: CGFloat

    var body: some View {
        Canvas { ctx, size in
            let pps = vm.pixelsPerSecond
            guard vm.duration > 0 else { return }

            let tickInterval: Double = pps < 8  ? 60 :
                                       pps < 14 ? 30 :
                                       pps < 25 ? 10 :
                                       pps < 60 ?  5 : 1

            var t = 0.0
            while t <= vm.duration + tickInterval {
                let x = CGFloat(t * pps)
                guard x <= size.width else { break }

                ctx.stroke(
                    Path { p in
                        p.move(to: CGPoint(x: x, y: size.height - 7))
                        p.addLine(to: CGPoint(x: x, y: size.height))
                    },
                    with: .color(.secondary.opacity(0.5)), lineWidth: 1
                )

                let m = Int(t) / 60, s = Int(t) % 60
                let label = m > 0 ? "\(m):\(String(format: "%02d", s))" : "\(Int(t))s"
                ctx.draw(
                    Text(label)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundColor(.secondary),
                    at: CGPoint(x: x + 3, y: size.height / 2 - 3),
                    anchor: .leading
                )
                t += tickInterval
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// MARK: - Interval Row (editable)
//
// Each row shows the *individual* intervals for that bird (or all_singing/all_dancing
// for .allBirds). The merged playback intervals live in birdRuntimes[].singingIntervals
// but those are not displayed here — keeping editing and playback cleanly separate.

struct IntervalRowView: View {
    let rowKey: RowKey
    @ObservedObject var vm: PlayerViewModel

    var body: some View {
        Canvas { ctx, size in
            let pps     = CGFloat(vm.pixelsPerSecond)
            let topH    = size.height * 0.48
            let bottomH = size.height * 0.44
            let singing = vm.displayIntervals(for: rowKey, type: .singing)
            let dancing = vm.displayIntervals(for: rowKey, type: .dancing)
            let sel     = vm.selectedInterval
            let handleW: CGFloat = 5

            // ── Dancing – bottom band (teal) ──
            for (i, interval) in dancing.enumerated() {
                let x    = CGFloat(interval.lowerBound) * pps
                let w    = max(2, CGFloat(interval.upperBound - interval.lowerBound) * pps)
                let rect = CGRect(x: x, y: size.height - bottomH - 2, width: w, height: bottomH)
                let isSel = sel == SelectedInterval(rowKey: rowKey, type: .dancing, index: i)
                ctx.fill(Path(roundedRect: rect, cornerRadius: 3),
                         with: .color(isSel ? Color.teal.opacity(0.9) : Color.teal.opacity(0.65)))
                if isSel {
                    ctx.stroke(Path(roundedRect: rect.insetBy(dx: -1.5, dy: -1.5), cornerRadius: 4),
                               with: .color(.white.opacity(0.85)), lineWidth: 2)
                }
                ctx.fill(Path(CGRect(x: x, y: rect.minY, width: handleW, height: rect.height)),
                         with: .color(.white.opacity(0.3)))
                ctx.fill(Path(CGRect(x: x + w - handleW, y: rect.minY, width: handleW, height: rect.height)),
                         with: .color(.white.opacity(0.3)))
            }

            // ── Singing – top band (orange) ──
            for (i, interval) in singing.enumerated() {
                let x    = CGFloat(interval.lowerBound) * pps
                let w    = max(2, CGFloat(interval.upperBound - interval.lowerBound) * pps)
                let rect = CGRect(x: x, y: 2, width: w, height: topH)
                let isSel = sel == SelectedInterval(rowKey: rowKey, type: .singing, index: i)
                ctx.fill(Path(roundedRect: rect, cornerRadius: 3),
                         with: .color(isSel ? Color.orange : Color.orange.opacity(0.82)))
                if isSel {
                    ctx.stroke(Path(roundedRect: rect.insetBy(dx: -1.5, dy: -1.5), cornerRadius: 4),
                               with: .color(.white.opacity(0.85)), lineWidth: 2)
                }
                ctx.fill(Path(CGRect(x: x, y: rect.minY, width: handleW, height: rect.height)),
                         with: .color(.white.opacity(0.3)))
                ctx.fill(Path(CGRect(x: x + w - handleW, y: rect.minY, width: handleW, height: rect.height)),
                         with: .color(.white.opacity(0.3)))
            }

            // Centre divider hint
            ctx.stroke(
                Path { p in
                    p.move(to: CGPoint(x: 0, y: size.height / 2))
                    p.addLine(to: CGPoint(x: size.width, y: size.height / 2))
                },
                with: .color(.secondary.opacity(0.15)), lineWidth: 0.5
            )
        }
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(EditableIntervalOverlay(vm: vm, rowKey: rowKey))
    }
}

// MARK: - Mouse Seek Overlay
//
// A transparent NSView that captures mouse button events (click / drag) for
// seeking while explicitly forwarding NSScrollWheel events up the responder
// chain to the enclosing NSScrollView. This avoids SwiftUI DragGesture
// conflicting with two-finger trackpad scrolling on macOS.

struct MouseSeekOverlay: NSViewRepresentable {
    let pixelsPerSecond: Double
    let duration: Double
    let onSeek: (Double) -> Void

    func makeNSView(context: Context) -> SeekNSView {
        SeekNSView(pixelsPerSecond: pixelsPerSecond, duration: duration, onSeek: onSeek)
    }

    func updateNSView(_ nsView: SeekNSView, context: Context) {
        nsView.pixelsPerSecond = pixelsPerSecond
        nsView.duration = duration
        nsView.onSeek = onSeek
    }

    // MARK: -

    class SeekNSView: NSView {
        var pixelsPerSecond: Double
        var duration: Double
        var onSeek: (Double) -> Void

        init(pixelsPerSecond: Double, duration: Double, onSeek: @escaping (Double) -> Void) {
            self.pixelsPerSecond = pixelsPerSecond
            self.duration = duration
            self.onSeek = onSeek
            super.init(frame: .zero)
        }
        required init?(coder: NSCoder) { fatalError() }

        // Accept first mouse so a click on an inactive window also seeks.
        override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

        private func seek(from event: NSEvent) {
            guard duration > 0 else { return }
            let x = convert(event.locationInWindow, from: nil).x
            let t = max(0, min(Double(x) / pixelsPerSecond, duration))
            onSeek(t)
        }

        override func mouseDown(with event: NSEvent)    { seek(from: event) }
        override func mouseDragged(with event: NSEvent) { seek(from: event) }

        // scrollWheel is intentionally NOT overridden.
        // AppKit's default NSView.scrollWheel() propagates the event up the
        // responder chain naturally, reaching the correct SwiftUI-managed
        // NSScrollView without any manual forwarding that could hit a wrong
        // ancestor scroll view and shift a parent container.
    }
}

// MARK: - Editable Interval Overlay
//
// Transparent NSView placed as an overlay on each IntervalRowView. Handles:
//   • Click / drag on empty space   → seek playhead
//   • Double-click on empty space   → add 1-second interval
//   • Drag left or right edge       → resize interval
//   • Click body of interval        → select it
//   • Right-click on interval       → context menu (Delete)
//   • Delete / Backspace key        → remove selected interval
//
// scrollWheel is intentionally not overridden so AppKit propagates scroll
// events to the enclosing NSScrollView for native two-finger trackpad scrolling.

struct EditableIntervalOverlay: NSViewRepresentable {
    let vm: PlayerViewModel   // strong ref — ViewModel outlives any NSView
    let rowKey: RowKey

    func makeNSView(context: Context) -> EditableIntervalNSView {
        EditableIntervalNSView(vm: vm, rowKey: rowKey,
                               pixelsPerSecond: vm.pixelsPerSecond,
                               duration: vm.duration)
    }

    func updateNSView(_ nsView: EditableIntervalNSView, context: Context) {
        nsView.pixelsPerSecond = vm.pixelsPerSecond
        nsView.duration = vm.duration
        nsView.window?.invalidateCursorRects(for: nsView)
    }
}

class EditableIntervalNSView: NSView {
    let vm: PlayerViewModel
    let rowKey: RowKey
    var pixelsPerSecond: Double
    var duration: Double

    private let edgeSlop: CGFloat = 8
    private var trackingArea: NSTrackingArea?

    enum DragState {
        case seekEmpty
        case resizingLeft(type: IntervalType, index: Int, anchorRight: Double)
        case resizingRight(type: IntervalType, index: Int, anchorLeft: Double)
        case movingBody(type: IntervalType, index: Int, width: Double, grabOffset: Double)
    }
    private var dragState: DragState?
    private var undoPushedForCurrentDrag = false

    init(vm: PlayerViewModel, rowKey: RowKey, pixelsPerSecond: Double, duration: Double) {
        self.vm = vm
        self.rowKey = rowKey
        self.pixelsPerSecond = pixelsPerSecond
        self.duration = duration
        super.init(frame: .zero)
    }
    required init?(coder: NSCoder) { fatalError() }

    override var acceptsFirstResponder: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let ta = trackingArea { removeTrackingArea(ta) }
        trackingArea = NSTrackingArea(
            rect: bounds,
            options: [.activeInKeyWindow, .mouseMoved, .mouseEnteredAndExited, .inVisibleRect],
            owner: self, userInfo: nil
        )
        addTrackingArea(trackingArea!)
    }

    // MARK: - Coordinate Helpers

    private func localPoint(_ event: NSEvent) -> CGPoint {
        convert(event.locationInWindow, from: nil)
    }

    private func time(fromX x: CGFloat) -> Double {
        let cap = duration > 0 ? duration : 1_000_000.0
        return max(0, min(Double(x) / pixelsPerSecond, cap))
    }

    // AppKit: y increases upward; y > midY → top of view → SwiftUI top half → singing.
    private func intervalType(forY y: CGFloat) -> IntervalType {
        y > bounds.midY ? .singing : .dancing
    }

    // MARK: - Hit Testing

    private struct HitResult {
        enum EdgeSide { case left, right }
        let type: IntervalType
        let index: Int
        let edge: EdgeSide?
    }

    private func hitTest(at point: CGPoint) -> HitResult? {
        let type = intervalType(forY: point.y)
        let intervals = vm.displayIntervals(for: rowKey, type: type)
        let x = point.x
        let pps = CGFloat(pixelsPerSecond)
        // Iterate in reverse so later-drawn (visually top) interval wins on overlap
        for (i, interval) in intervals.enumerated().reversed() {
            let left  = CGFloat(interval.lowerBound) * pps
            let right = CGFloat(interval.upperBound) * pps
            guard right >= left else { continue }
            if abs(x - left) <= edgeSlop && x <= right + edgeSlop {
                return HitResult(type: type, index: i, edge: .left)
            }
            if abs(x - right) <= edgeSlop && x >= left - edgeSlop {
                return HitResult(type: type, index: i, edge: .right)
            }
            if x > left + edgeSlop && x < right - edgeSlop {
                return HitResult(type: type, index: i, edge: nil)
            }
        }
        return nil
    }

    // MARK: - Mouse Events

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
        let point = localPoint(event)
        undoPushedForCurrentDrag = false

        // Double-click: add interval ONLY if not on an existing interval.
        if event.clickCount == 2 {
            if hitTest(at: point) == nil {
                let type = intervalType(forY: point.y)
                let t = time(fromX: point.x)
                let lo = max(0, t - 0.5)
                let hi = min(lo + 1.0, duration > 0 ? duration : lo + 1.0)
                vm.addInterval(lo...hi, rowKey: rowKey, type: type)
            }
            dragState = nil
            return
        }

        if let hit = hitTest(at: point) {
            let intervals = vm.displayIntervals(for: rowKey, type: hit.type)
            guard intervals.indices.contains(hit.index) else { return }
            let range = intervals[hit.index]
            vm.selectedInterval = SelectedInterval(rowKey: rowKey, type: hit.type, index: hit.index)
            switch hit.edge {
            case .left:  dragState = .resizingLeft(type: hit.type, index: hit.index, anchorRight: range.upperBound)
            case .right: dragState = .resizingRight(type: hit.type, index: hit.index, anchorLeft: range.lowerBound)
            case .none:
                let grabOffset = time(fromX: point.x) - range.lowerBound
                dragState = .movingBody(type: hit.type, index: hit.index,
                                        width: range.upperBound - range.lowerBound,
                                        grabOffset: grabOffset)
            }
        } else {
            vm.selectedInterval = nil
            dragState = .seekEmpty
            if duration > 0 { vm.seek(to: time(fromX: point.x)) }
        }
    }

    override func mouseDragged(with event: NSEvent) {
        let t = time(fromX: localPoint(event).x)
        // Push one undo entry at the start of a drag (not on every moved pixel)
        if !undoPushedForCurrentDrag, case .some = dragState {
            if case .seekEmpty = dragState { } else {
                vm.beginIntervalUpdate()
                undoPushedForCurrentDrag = true
            }
        }
        switch dragState {
        case .resizingLeft(let type, let index, let anchorRight):
            let newLeft = max(0, min(t, anchorRight - 0.05))
            vm.updateInterval(at: index, rowKey: rowKey, type: type, newRange: newLeft...anchorRight)
        case .resizingRight(let type, let index, let anchorLeft):
            let cap = duration > 0 ? duration : t
            let newRight = max(anchorLeft + 0.05, min(t, cap))
            vm.updateInterval(at: index, rowKey: rowKey, type: type, newRange: anchorLeft...newRight)
        case .movingBody(let type, let index, let width, let grabOffset):
            let cap = duration > 0 ? duration : t
            let newLeft  = max(0, min(t - grabOffset, cap - width))
            let newRight = newLeft + width
            vm.updateInterval(at: index, rowKey: rowKey, type: type, newRange: newLeft...newRight)
        case .seekEmpty:
            if duration > 0 { vm.seek(to: t) }
        case nil:
            break
        }
    }

    override func mouseUp(with event: NSEvent) { dragState = nil }

    // MARK: - Cursor

    override func mouseMoved(with event: NSEvent)  { updateCursor(for: localPoint(event)) }
    override func mouseEntered(with event: NSEvent) { updateCursor(for: localPoint(event)) }
    override func mouseExited(with event: NSEvent)  { NSCursor.arrow.set() }

    private func updateCursor(for point: CGPoint) {
        guard let hit = hitTest(at: point) else { NSCursor.arrow.set(); return }
        switch hit.edge {
        case .left, .right: NSCursor.resizeLeftRight.set()
        case .none:         NSCursor.openHand.set()
        }
    }

    // MARK: - Context Menu

    override func rightMouseDown(with event: NSEvent) {
        let point = localPoint(event)
        guard let hit = hitTest(at: point) else { super.rightMouseDown(with: event); return }
        vm.selectedInterval = SelectedInterval(rowKey: rowKey, type: hit.type, index: hit.index)

        let menu = NSMenu(title: "")
        let header = NSMenuItem(title: "\(hit.type == .singing ? "Singing" : "Dancing") Interval",
                                action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        menu.addItem(.separator())
        let del = NSMenuItem(title: "Delete", action: #selector(deleteSelected), keyEquivalent: "")
        del.target = self
        menu.addItem(del)
        NSMenu.popUpContextMenu(menu, with: event, for: self)
    }

    @objc private func deleteSelected() {
        guard let sel = vm.selectedInterval, sel.rowKey == rowKey else { return }
        vm.removeInterval(at: sel.index, rowKey: sel.rowKey, type: sel.type)
    }

    // MARK: - Keyboard

    override func keyDown(with event: NSEvent) {
        let cmd = event.modifierFlags.contains(.command)
        let shift = event.modifierFlags.contains(.shift)
        if event.keyCode == 51 || event.keyCode == 117 { // backspace / forward-delete
            deleteSelected()
        } else if cmd && shift && event.charactersIgnoringModifiers == "z" {
            vm.redo()
        } else if cmd && !shift && event.charactersIgnoringModifiers == "z" {
            vm.undo()
        } else {
            super.keyDown(with: event)
        }
    }
}

// MARK: - Auto-Scroll Driver
//
// A zero-size NSViewRepresentable that locates the nearest enclosing NSScrollView
// and programmatically scrolls it to keep the playhead centered during playback.
// Observes NSScrollViewWillStartLiveScroll to stop auto-scroll when the user
// manually swipes.

struct TimelineAutoScroller: NSViewRepresentable {
    @ObservedObject var vm: PlayerViewModel
    let viewportWidth: CGFloat

    func makeNSView(context: Context) -> AutoScrollNSView {
        AutoScrollNSView(vm: vm)
    }

    func updateNSView(_ nsView: AutoScrollNSView, context: Context) {
        nsView.viewportWidth = viewportWidth
        nsView.update()
    }

    class AutoScrollNSView: NSView {
        let vm: PlayerViewModel
        var viewportWidth: CGFloat = 0
        private var scrollView: NSScrollView? { findScrollView() }
        private var observations: [Any] = []

        init(vm: PlayerViewModel) {
            self.vm = vm
            super.init(frame: .zero)
        }
        required init?(coder: NSCoder) { fatalError() }

        override func viewDidMoveToSuperview() {
            super.viewDidMoveToSuperview()
            observations.removeAll()
            // Listen for live-scroll start (two-finger swipe or scroll bar drag)
            let nc = NotificationCenter.default
            observations.append(
                nc.addObserver(forName: NSScrollView.willStartLiveScrollNotification,
                               object: nil, queue: .main) { [weak self] notif in
                    // Only disable if it's our scroll view
                    guard let sv = self?.scrollView,
                          (notif.object as? NSScrollView) === sv else { return }
                    self?.vm.userDidManuallyScroll()
                }
            )
        }

        func update() {
            guard vm.autoScrollEnabled, vm.isPlaying, vm.duration > 0 else { return }
            guard let sv = scrollView else { return }

            let playheadX = CGFloat(vm.currentTime * vm.pixelsPerSecond)
            let halfViewport = viewportWidth / 2
            // Only start scrolling once the playhead has passed the centre
            guard playheadX > halfViewport else { return }

            let targetX = playheadX - halfViewport
            let contentWidth = sv.documentView?.bounds.width ?? 0
            let maxX = max(0, contentWidth - viewportWidth)
            let clampedX = min(targetX, maxX)

            let currentX = sv.documentVisibleRect.origin.x
            // Only scroll if we'd move more than 1pt (avoids jitter)
            guard abs(clampedX - currentX) > 1 else { return }

            sv.documentView?.scroll(NSPoint(x: clampedX, y: 0))
        }

        private func findScrollView() -> NSScrollView? {
            var v: NSView? = superview
            while let candidate = v {
                if let sv = candidate as? NSScrollView { return sv }
                v = candidate.superview
            }
            return nil
        }
    }
}
