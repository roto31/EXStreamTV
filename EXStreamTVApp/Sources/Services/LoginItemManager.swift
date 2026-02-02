//
//  LoginItemManager.swift
//  EXStreamTVApp
//
//  Manages "Launch at Login" functionality using SMAppService (macOS 13+).
//

import Foundation
import ServiceManagement

/// Manages the app's login item status for automatic startup at login.
class LoginItemManager {
    
    // MARK: - Singleton
    
    static let shared = LoginItemManager()
    
    private init() {}
    
    // MARK: - Public Methods
    
    /// Enable or disable launch at login.
    /// - Parameter enabled: Whether the app should launch at login.
    /// - Returns: True if the operation succeeded, false otherwise.
    @discardableResult
    static func setLaunchAtLogin(enabled: Bool) -> Bool {
        if #available(macOS 13.0, *) {
            do {
                if enabled {
                    try SMAppService.mainApp.register()
                    print("[LoginItemManager] Registered as login item")
                } else {
                    try SMAppService.mainApp.unregister()
                    print("[LoginItemManager] Unregistered from login items")
                }
                return true
            } catch {
                print("[LoginItemManager] Failed to update login item: \(error.localizedDescription)")
                return false
            }
        } else {
            // Fallback for older macOS versions
            print("[LoginItemManager] SMAppService requires macOS 13.0+")
            return false
        }
    }
    
    /// Check if the app is currently set to launch at login.
    static var isEnabled: Bool {
        if #available(macOS 13.0, *) {
            return SMAppService.mainApp.status == .enabled
        }
        return false
    }
    
    /// Get the current status of the login item.
    static var status: LoginItemStatus {
        if #available(macOS 13.0, *) {
            switch SMAppService.mainApp.status {
            case .enabled:
                return .enabled
            case .notRegistered:
                return .notRegistered
            case .requiresApproval:
                return .requiresApproval
            case .notFound:
                return .notFound
            @unknown default:
                return .unknown
            }
        }
        return .unavailable
    }
    
    /// Toggle the launch at login setting.
    /// - Returns: The new state after toggling.
    @discardableResult
    static func toggle() -> Bool {
        let newState = !isEnabled
        setLaunchAtLogin(enabled: newState)
        return isEnabled
    }
    
    /// Open System Settings to the Login Items pane (for user to manually approve if needed).
    static func openLoginItemsSettings() {
        if #available(macOS 13.0, *) {
            if let url = URL(string: "x-apple.systempreferences:com.apple.LoginItems-Settings.extension") {
                NSWorkspace.shared.open(url)
            }
        } else {
            // Fallback for older macOS
            if let url = URL(string: "x-apple.systempreferences:com.apple.preference.users") {
                NSWorkspace.shared.open(url)
            }
        }
    }
}

// MARK: - Login Item Status

enum LoginItemStatus: String {
    case enabled = "Enabled"
    case notRegistered = "Not Registered"
    case requiresApproval = "Requires Approval"
    case notFound = "Not Found"
    case unknown = "Unknown"
    case unavailable = "Unavailable (macOS 13+ required)"
    
    var description: String {
        return self.rawValue
    }
    
    var isActive: Bool {
        return self == .enabled
    }
    
    var needsUserAction: Bool {
        return self == .requiresApproval
    }
}
