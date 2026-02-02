//
//  HotkeyManager.swift
//  EXStreamTVApp
//
//  Global keyboard shortcut manager using Carbon HotKey API.
//

import AppKit
import Carbon

/// Manages global keyboard shortcuts for the application.
@MainActor
class HotkeyManager: ObservableObject {
    // MARK: - Types
    
    /// Available hotkey actions
    enum HotkeyAction: String, CaseIterable, Identifiable {
        case startServer = "startServer"
        case stopServer = "stopServer"
        case restartServer = "restartServer"
        case openWebUI = "openWebUI"
        case openDashboard = "openDashboard"
        case toggleMenu = "toggleMenu"
        
        var id: String { rawValue }
        
        var displayName: String {
            switch self {
            case .startServer: return "Start Server"
            case .stopServer: return "Stop Server"
            case .restartServer: return "Restart Server"
            case .openWebUI: return "Open Web UI"
            case .openDashboard: return "Open Dashboard"
            case .toggleMenu: return "Show Menu"
            }
        }
        
        var defaultKeyCombo: KeyCombo {
            switch self {
            case .startServer:
                return KeyCombo(key: .s, modifiers: [.control, .option])
            case .stopServer:
                return KeyCombo(key: .x, modifiers: [.control, .option])
            case .restartServer:
                return KeyCombo(key: .r, modifiers: [.control, .option])
            case .openWebUI:
                return KeyCombo(key: .o, modifiers: [.control, .option])
            case .openDashboard:
                return KeyCombo(key: .d, modifiers: [.control, .option])
            case .toggleMenu:
                return KeyCombo(key: .space, modifiers: [.control, .option])
            }
        }
    }
    
    /// Represents a key combination
    struct KeyCombo: Equatable, Codable {
        let key: KeyCode
        let modifiers: ModifierFlags
        
        var displayString: String {
            var parts: [String] = []
            if modifiers.contains(.control) { parts.append("⌃") }
            if modifiers.contains(.option) { parts.append("⌥") }
            if modifiers.contains(.shift) { parts.append("⇧") }
            if modifiers.contains(.command) { parts.append("⌘") }
            parts.append(key.displayString)
            return parts.joined()
        }
        
        var carbonModifiers: UInt32 {
            var carbonMods: UInt32 = 0
            if modifiers.contains(.control) { carbonMods |= UInt32(controlKey) }
            if modifiers.contains(.option) { carbonMods |= UInt32(optionKey) }
            if modifiers.contains(.shift) { carbonMods |= UInt32(shiftKey) }
            if modifiers.contains(.command) { carbonMods |= UInt32(cmdKey) }
            return carbonMods
        }
    }
    
    /// Key codes for Carbon API
    enum KeyCode: UInt32, Codable {
        case a = 0x00, s = 0x01, d = 0x02, f = 0x03, h = 0x04, g = 0x05
        case z = 0x06, x = 0x07, c = 0x08, v = 0x09, b = 0x0B, q = 0x0C
        case w = 0x0D, e = 0x0E, r = 0x0F, y = 0x10, t = 0x11, o = 0x1F
        case u = 0x20, i = 0x22, p = 0x23, l = 0x25, j = 0x26, k = 0x28
        case n = 0x2D, m = 0x2E
        case space = 0x31
        case num0 = 0x1D, num1 = 0x12, num2 = 0x13, num3 = 0x14
        case num4 = 0x15, num5 = 0x17, num6 = 0x16, num7 = 0x1A
        case num8 = 0x1C, num9 = 0x19
        
        var displayString: String {
            switch self {
            case .a: return "A"
            case .s: return "S"
            case .d: return "D"
            case .f: return "F"
            case .h: return "H"
            case .g: return "G"
            case .z: return "Z"
            case .x: return "X"
            case .c: return "C"
            case .v: return "V"
            case .b: return "B"
            case .q: return "Q"
            case .w: return "W"
            case .e: return "E"
            case .r: return "R"
            case .y: return "Y"
            case .t: return "T"
            case .o: return "O"
            case .u: return "U"
            case .i: return "I"
            case .p: return "P"
            case .l: return "L"
            case .j: return "J"
            case .k: return "K"
            case .n: return "N"
            case .m: return "M"
            case .space: return "Space"
            case .num0: return "0"
            case .num1: return "1"
            case .num2: return "2"
            case .num3: return "3"
            case .num4: return "4"
            case .num5: return "5"
            case .num6: return "6"
            case .num7: return "7"
            case .num8: return "8"
            case .num9: return "9"
            }
        }
    }
    
    /// Modifier flags
    struct ModifierFlags: OptionSet, Codable {
        let rawValue: Int
        
        static let control = ModifierFlags(rawValue: 1 << 0)
        static let option = ModifierFlags(rawValue: 1 << 1)
        static let shift = ModifierFlags(rawValue: 1 << 2)
        static let command = ModifierFlags(rawValue: 1 << 3)
    }
    
    // MARK: - Properties
    
    static let shared = HotkeyManager()
    
    @Published var isEnabled: Bool = true {
        didSet {
            if isEnabled {
                registerAllHotkeys()
            } else {
                unregisterAllHotkeys()
            }
            saveSettings()
        }
    }
    
    @Published var hotkeys: [HotkeyAction: KeyCombo] = [:]
    
    private var registeredHotkeys: [HotkeyAction: (id: UInt32, ref: EventHotKeyRef?)] = [:]
    private var nextHotkeyId: UInt32 = 1
    private var eventHandler: EventHandlerRef?
    
    // Action handlers
    var onStartServer: (() -> Void)?
    var onStopServer: (() -> Void)?
    var onRestartServer: (() -> Void)?
    var onOpenWebUI: (() -> Void)?
    var onOpenDashboard: (() -> Void)?
    var onToggleMenu: (() -> Void)?
    
    // MARK: - Initialization
    
    private init() {
        loadSettings()
        installEventHandler()
    }
    
    deinit {
        unregisterAllHotkeys()
        if let handler = eventHandler {
            RemoveEventHandler(handler)
        }
    }
    
    // MARK: - Public Methods
    
    /// Registers all configured hotkeys
    func registerAllHotkeys() {
        guard isEnabled else { return }
        
        unregisterAllHotkeys()
        
        for (action, keyCombo) in hotkeys {
            registerHotkey(action: action, keyCombo: keyCombo)
        }
    }
    
    /// Unregisters all hotkeys
    func unregisterAllHotkeys() {
        for (_, value) in registeredHotkeys {
            if let ref = value.ref {
                UnregisterEventHotKey(ref)
            }
        }
        registeredHotkeys.removeAll()
    }
    
    /// Updates a hotkey for a specific action
    /// - Parameters:
    ///   - action: The action to update
    ///   - keyCombo: The new key combination
    func updateHotkey(_ action: HotkeyAction, to keyCombo: KeyCombo) {
        // Unregister existing hotkey for this action
        if let existing = registeredHotkeys[action], let ref = existing.ref {
            UnregisterEventHotKey(ref)
            registeredHotkeys.removeValue(forKey: action)
        }
        
        // Update and register new hotkey
        hotkeys[action] = keyCombo
        registerHotkey(action: action, keyCombo: keyCombo)
        saveSettings()
    }
    
    /// Removes a hotkey for a specific action
    /// - Parameter action: The action to remove the hotkey for
    func removeHotkey(_ action: HotkeyAction) {
        if let existing = registeredHotkeys[action], let ref = existing.ref {
            UnregisterEventHotKey(ref)
            registeredHotkeys.removeValue(forKey: action)
        }
        hotkeys.removeValue(forKey: action)
        saveSettings()
    }
    
    /// Resets all hotkeys to defaults
    func resetToDefaults() {
        unregisterAllHotkeys()
        hotkeys.removeAll()
        
        for action in HotkeyAction.allCases {
            hotkeys[action] = action.defaultKeyCombo
        }
        
        registerAllHotkeys()
        saveSettings()
    }
    
    /// Gets the display string for a hotkey action
    func displayString(for action: HotkeyAction) -> String {
        return hotkeys[action]?.displayString ?? "Not Set"
    }
    
    // MARK: - Private Methods
    
    private func installEventHandler() {
        var eventSpec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        
        let status = InstallEventHandler(
            GetEventDispatcherTarget(),
            { (_, event, userData) -> OSStatus in
                guard let userData = userData else { return OSStatus(eventNotHandledErr) }
                let manager = Unmanaged<HotkeyManager>.fromOpaque(userData).takeUnretainedValue()
                return manager.handleHotkeyEvent(event)
            },
            1,
            &eventSpec,
            Unmanaged.passUnretained(self).toOpaque(),
            &eventHandler
        )
        
        if status != noErr {
            print("Failed to install hotkey event handler: \(status)")
        }
    }
    
    private func handleHotkeyEvent(_ event: EventRef?) -> OSStatus {
        guard let event = event else { return OSStatus(eventNotHandledErr) }
        
        var hotkeyId = EventHotKeyID()
        let status = GetEventParameter(
            event,
            UInt32(kEventParamDirectObject),
            UInt32(typeEventHotKeyID),
            nil,
            MemoryLayout<EventHotKeyID>.size,
            nil,
            &hotkeyId
        )
        
        guard status == noErr else { return OSStatus(eventNotHandledErr) }
        
        // Find the action for this hotkey ID
        for (action, value) in registeredHotkeys {
            if value.id == hotkeyId.id {
                DispatchQueue.main.async { [weak self] in
                    self?.executeAction(action)
                }
                return noErr
            }
        }
        
        return OSStatus(eventNotHandledErr)
    }
    
    private func executeAction(_ action: HotkeyAction) {
        switch action {
        case .startServer:
            onStartServer?()
        case .stopServer:
            onStopServer?()
        case .restartServer:
            onRestartServer?()
        case .openWebUI:
            onOpenWebUI?()
        case .openDashboard:
            onOpenDashboard?()
        case .toggleMenu:
            onToggleMenu?()
        }
    }
    
    private func registerHotkey(action: HotkeyAction, keyCombo: KeyCombo) {
        let hotkeyId = nextHotkeyId
        nextHotkeyId += 1
        
        var eventHotKeyId = EventHotKeyID()
        eventHotKeyId.signature = OSType(0x4558_5456) // "EXTV"
        eventHotKeyId.id = hotkeyId
        
        var hotKeyRef: EventHotKeyRef?
        
        let status = RegisterEventHotKey(
            keyCombo.key.rawValue,
            keyCombo.carbonModifiers,
            eventHotKeyId,
            GetEventDispatcherTarget(),
            0,
            &hotKeyRef
        )
        
        if status == noErr {
            registeredHotkeys[action] = (id: hotkeyId, ref: hotKeyRef)
        } else {
            print("Failed to register hotkey for \(action): \(status)")
        }
    }
    
    // MARK: - Persistence
    
    private func loadSettings() {
        isEnabled = UserDefaults.standard.bool(forKey: "hotkeysEnabled")
        
        // Load custom hotkeys or use defaults
        if let data = UserDefaults.standard.data(forKey: "customHotkeys"),
           let decoded = try? JSONDecoder().decode([String: KeyCombo].self, from: data) {
            for (key, value) in decoded {
                if let action = HotkeyAction(rawValue: key) {
                    hotkeys[action] = value
                }
            }
        }
        
        // Fill in any missing defaults
        for action in HotkeyAction.allCases {
            if hotkeys[action] == nil {
                hotkeys[action] = action.defaultKeyCombo
            }
        }
        
        // Default to enabled if not set
        if !UserDefaults.standard.bool(forKey: "hotkeysSettingsInitialized") {
            isEnabled = true
            UserDefaults.standard.set(true, forKey: "hotkeysEnabled")
            UserDefaults.standard.set(true, forKey: "hotkeysSettingsInitialized")
        }
    }
    
    private func saveSettings() {
        UserDefaults.standard.set(isEnabled, forKey: "hotkeysEnabled")
        
        var hotkeyDict: [String: KeyCombo] = [:]
        for (action, keyCombo) in hotkeys {
            hotkeyDict[action.rawValue] = keyCombo
        }
        
        if let data = try? JSONEncoder().encode(hotkeyDict) {
            UserDefaults.standard.set(data, forKey: "customHotkeys")
        }
    }
}
