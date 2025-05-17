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


class BirdPiViewModel: NSObject, ObservableObject {
    var songsDict = [String: Int]()
    @Published var songDisplayNames: [String]
    @Published var isConnected: Bool = false
    @Published var selectedIndex: Int? = nil
    @Published var errorMessage: String? = nil
    @Published var sortState: SortState = .unsorted

    private var centralManager: CBCentralManager!
    private var birdPiPeripheral: CBPeripheral?
    private var connectionTimeoutTimer: Timer?

    private var displayNamesChar: CBCharacteristic?
    private var indexSelectChar: CBCharacteristic?

    private let serviceUUID = CBUUID(string: "12345678-0000-0000-0000-abcdefabcdef")
    private let displayNamesUUID = CBUUID(string: "abcd1111-2222-3333-4444-555566667777")
    private let indexSelectUUID = CBUUID(string: "abcd8888-9999-aaaa-bbbb-ccccdddddddd")

    private let connectionTimeout: TimeInterval = 10.0
    private var pingTimer: Timer?

    init(songNames: [String] = []) {
        self.songDisplayNames = songNames
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: .main)
        startConnectionTimeout()
        startPings()
    }
    
    func sortSongsByName(order: SortOrder? = nil) {
        guard let order else {
            songDisplayNames = songsDict.keys.sorted {
                songsDict[$0]! < songsDict[$1]!
            }
            return
        }
        if order == .forward {
            songDisplayNames = songsDict.keys.sorted(by: <)
        }
        else {
            songDisplayNames = songsDict.keys.sorted(by: >)
        }
    }

    func sendSelectedSong(_ song: String) {
        guard let peripheral = birdPiPeripheral,
              let writeChar = indexSelectChar else {
            print("❌ BLE not connected or characteristic not ready")
            errorMessage = "Not connected"
            return
        }
        let index = songsDict[song] ?? -1
        let data = "\(index)".data(using: .utf8)!
        peripheral.writeValue(data, for: writeChar, type: .withoutResponse)
        selectedIndex = index
        print("📤 Sent index: \(index)")
//        if selectedIndex == -1 {
//            restartScan()
//        }
    }
    
    func toggleSortState() {
        sortState.toggle()
        sortSongsByName(order: sortState.sortOrder)
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
//        songDisplayNames = []
        centralManager.scanForPeripherals(withServices: [serviceUUID], options: nil)
        startConnectionTimeout()
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
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let services = peripheral.services else { return }
        for service in services {
            peripheral.discoverCharacteristics([displayNamesUUID, indexSelectUUID], for: service)
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
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if characteristic.uuid == displayNamesUUID,
           let data = characteristic.value,
           let jsonString = String(data: data, encoding: .utf8),
           let decoded = try? JSONDecoder().decode([String].self, from: Data(jsonString.utf8)) {
            print("🎶 Song list received: \(decoded)")

            songsDict.removeAll()
            for (index, song) in decoded.enumerated() {
                print("\(index): \(song)")
                songsDict[song] = index
            }
            sortSongsByName(order: sortState.sortOrder)
        }
    }
    
    func startPings() {
        pingTimer = Timer.scheduledTimer(withTimeInterval: 25.0, repeats: true) { [weak self] _ in
            guard let self = self,
                  let peripheral = self.birdPiPeripheral,
                  let displayChar = self.displayNamesChar else {
                self?.pingTimer?.invalidate();
                return
            }
            peripheral.readValue(for: displayChar)
        }
    }
}
