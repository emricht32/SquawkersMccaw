//
//  BirdPiViewModel.swift
//  MoaiLanai
//
//  Created by Jon Emrich on 5/12/25.
//


import Foundation
import CoreBluetooth
import Combine

enum SortState {
    case unsorted
    case ascending
    case descending

    mutating func toggle() {
        switch self {
        case .unsorted: self = .ascending
        case .ascending: self = .descending
        case .descending: self = .unsorted
        }
    }
    
    var sortOrder: SortOrder? {
        switch self {
        case .unsorted: return nil
        case .ascending: return .forward
        case .descending: return .reverse
        }
    }
}

struct SongStateUpdate: Codable {
    let status: String
    let index: Int
}

struct Song: Equatable, Codable {
    static func == (lhs: Song, rhs: Song) -> Bool {
        lhs.name == rhs.name && lhs.index == rhs.index
    }
    
    enum State: Codable {
        case notPlaying
        case reqesting
        case playing
    }
    let name: String
    let index: Int
    var state: State = .notPlaying
}

class BirdPiViewModel: NSObject, ObservableObject {
    var songsDict = [String: Int]()
//    @Published var songDisplayNames: [String]
    @Published var isConnected: Bool = false
    @Published var errorMessage: String? = nil
    @Published var sortState: SortState = .unsorted
    @Published var songs: [Song] = []

    private var centralManager: CBCentralManager!
    private var birdPiPeripheral: CBPeripheral?
    private var connectionTimeoutTimer: Timer?

    private var displayNamesChar: CBCharacteristic?
    private var indexSelectChar: CBCharacteristic?
    private var notifySongChar: CBCharacteristic?

    private let serviceUUID = CBUUID(string: "12345678-0000-0000-0000-abcdefabcdef")
    private let displayNamesUUID = CBUUID(string: "abcd1111-2222-3333-4444-555566667777")
    private let indexSelectUUID = CBUUID(string: "abcd8888-9999-aaaa-bbbb-ccccdddddddd")
    private let notifySongUUID = CBUUID(string: "abcdaaaa-bbbb-cccc-dddd-eeeeffffffff")

    private let connectionTimeout: TimeInterval = 10.0
    private var pingTimer: Timer?

    init(songs: [Song] = []) {
        self.songs = songs
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: .main)
        startConnectionTimeout()
    }
    
    func sortSongs(order: SortOrder? = nil) {
        guard let order else {
            songs = songs.sorted { $0.index < $1.index }
            return
        }
        songs = songs.sorted(by: order == .forward ? { $0.index < $1.index } : { $0.index > $1.index })
    }

    func sendSelected(_ song: Song) {
        var song = song
        guard let peripheral = birdPiPeripheral,
              let writeChar = indexSelectChar else {
            print("❌ BLE not connected or characteristic not ready")
            errorMessage = "Not connected"
            return
        }
        let index = song.index
        let data = "\(index)".data(using: .utf8)!
        peripheral.writeValue(data, for: writeChar, type: .withoutResponse)
        print("📤 Sent index: \(index)")
        song.state = .reqesting
        guard let idx = songs.firstIndex(of: song) else { return }
        songs[idx] = song
    }
    
    func toggleSortState() {
        sortState.toggle()
        sortSongs(order: sortState.sortOrder)
    }

    private func startConnectionTimeout() {
        connectionTimeoutTimer?.invalidate()
        connectionTimeoutTimer = Timer.scheduledTimer(withTimeInterval: connectionTimeout, repeats: false) {[weak self] _ in
            self?.errorMessage = "Connection timed out."
            self?.restartScan()
        }
    }

    private func cancelConnectionTimeout() {
        connectionTimeoutTimer?.invalidate()
        connectionTimeoutTimer = nil
    }

    private func restartScan() {
        print("🔁 Restarting scan...")
        isConnected = false
        birdPiPeripheral = nil
        displayNamesChar = nil
        indexSelectChar = nil
        centralManager.scanForPeripherals(withServices: [serviceUUID], options: nil)
        startConnectionTimeout()
    }
    
    func updateSongs(with update: SongStateUpdate){
        for var song in songs {
            song.state = .notPlaying
            if song.index == update.index {
                song.state = update.status == "finished" ? .notPlaying : .playing
            }
        }
    }
}

// MARK: - CBCentralManagerDelegate & CBPeripheralDelegate
extension BirdPiViewModel: CBCentralManagerDelegate, CBPeripheralDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            print("🔍 Scanning for BirdPi...")
            restartScan()
        } else {
            print("❌ Bluetooth not available")
            errorMessage = "Bluetooth is not available"
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String : Any], rssi RSSI: NSNumber) {
        print("📶 Discovered BirdPi: \(peripheral.name ?? "Unknown")")
        central.stopScan()
        cancelConnectionTimeout()
        birdPiPeripheral = peripheral
        birdPiPeripheral?.delegate = self
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("✅ Connected to BirdPi")
        isConnected = true
        cancelConnectionTimeout()
        peripheral.discoverServices([serviceUUID])
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        print("⚠️ Disconnected from BirdPi")
        isConnected = false
        restartScan()
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let services = peripheral.services else { return }
        for service in services {
            peripheral.discoverCharacteristics([displayNamesUUID, indexSelectUUID, notifySongUUID], for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard let characteristics = service.characteristics else { return }
        for characteristic in characteristics {
            if characteristic.uuid == displayNamesUUID {
                displayNamesChar = characteristic
                peripheral.readValue(for: characteristic)
                // Optional: subscribe to updates if BirdPi uses notify
                 peripheral.setNotifyValue(true, for: characteristic)
            } else if characteristic.uuid == indexSelectUUID {
                indexSelectChar = characteristic
            } else if characteristic.uuid == notifySongUUID {
                notifySongChar = characteristic
                peripheral.setNotifyValue(true, for: characteristic)
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if characteristic.uuid == displayNamesUUID,
           let data = characteristic.value,
           let jsonString = String(data: data, encoding: .utf8),
           let decoded = try? JSONDecoder().decode([String].self, from: Data(jsonString.utf8)) {
            print("🎶 Song list received: \(decoded)")
            
            for (index, name) in decoded.enumerated() {
                let song = Song(name: name, index: index)
                print("\(index): \(song)")
                if songs.contains(song) { continue }
                songs.append(song)
            }
            sortSongs(order: sortState.sortOrder)
        }
        else if characteristic.uuid == notifySongUUID,
//            {"status": "playing", "index": 2}
            let data = characteristic.value,
            let jsonString = String(data: data, encoding: .utf8),
            let update = try? JSONDecoder().decode(SongStateUpdate.self, from: Data(jsonString.utf8)) {
            updateSongs(with: update)
        }
    }
}
