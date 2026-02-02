//
//  NotificationManager.swift
//  EXStreamTVApp
//
//  Manages macOS system notifications for EXStreamTV.
//

import Foundation
import UserNotifications

/// Notification types used by EXStreamTV
enum EXStreamNotificationType: String {
    case serverStarted = "server_started"
    case serverStopped = "server_stopped"
    case serverError = "server_error"
    case streamStarted = "stream_started"
    case streamEnded = "stream_ended"
    case channelCreated = "channel_created"
    case aiFix = "ai_fix"
    case update = "update_available"
}

/// Manages system notifications
@MainActor
class NotificationManager: NSObject, ObservableObject {
    
    // MARK: - Singleton
    
    static let shared = NotificationManager()
    
    // MARK: - Published Properties
    
    @Published var isAuthorized = false
    @Published var pendingNotifications: [UNNotificationRequest] = []
    
    // MARK: - Properties
    
    private let center = UNUserNotificationCenter.current()
    
    // MARK: - Initialization
    
    override init() {
        super.init()
        center.delegate = self
        checkAuthorizationStatus()
    }
    
    // MARK: - Authorization
    
    /// Request notification permissions
    func requestAuthorization() async -> Bool {
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            isAuthorized = granted
            return granted
        } catch {
            print("[NotificationManager] Authorization error: \(error)")
            return false
        }
    }
    
    /// Check current authorization status
    func checkAuthorizationStatus() {
        center.getNotificationSettings { [weak self] settings in
            Task { @MainActor in
                self?.isAuthorized = settings.authorizationStatus == .authorized
            }
        }
    }
    
    // MARK: - Sending Notifications
    
    /// Send a notification
    func send(
        type: EXStreamNotificationType,
        title: String,
        body: String,
        subtitle: String? = nil,
        sound: Bool = true,
        actionURL: URL? = nil
    ) {
        guard UserDefaults.standard.bool(forKey: "showNotifications") else { return }
        
        // Check specific notification settings
        switch type {
        case .serverStarted:
            guard UserDefaults.standard.bool(forKey: "notifyOnStart") else { return }
        case .serverStopped:
            guard UserDefaults.standard.bool(forKey: "notifyOnStop") else { return }
        case .serverError:
            guard UserDefaults.standard.bool(forKey: "notifyOnError") else { return }
        case .streamStarted:
            guard UserDefaults.standard.bool(forKey: "notifyOnStreamStart") else { return }
        default:
            break
        }
        
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        
        if let subtitle = subtitle {
            content.subtitle = subtitle
        }
        
        if sound {
            content.sound = .default
        }
        
        // Add custom data
        var userInfo: [String: Any] = [
            "type": type.rawValue
        ]
        
        if let actionURL = actionURL {
            userInfo["actionURL"] = actionURL.absoluteString
        }
        
        content.userInfo = userInfo
        
        // Set category for actions
        content.categoryIdentifier = type.rawValue
        
        // Create request
        let request = UNNotificationRequest(
            identifier: "\(type.rawValue)_\(Date().timeIntervalSince1970)",
            content: content,
            trigger: nil  // Deliver immediately
        )
        
        center.add(request) { error in
            if let error = error {
                print("[NotificationManager] Failed to send notification: \(error)")
            }
        }
    }
    
    /// Send server started notification
    func notifyServerStarted(port: Int) {
        send(
            type: .serverStarted,
            title: "EXStreamTV Server Started",
            body: "Server is running on port \(port)",
            subtitle: "Ready to stream",
            actionURL: URL(string: "http://localhost:\(port)")
        )
    }
    
    /// Send server stopped notification
    func notifyServerStopped() {
        send(
            type: .serverStopped,
            title: "EXStreamTV Server Stopped",
            body: "The streaming server has been stopped",
            sound: false
        )
    }
    
    /// Send server error notification
    func notifyServerError(_ error: String) {
        send(
            type: .serverError,
            title: "EXStreamTV Error",
            body: error,
            subtitle: "Server encountered an issue"
        )
    }
    
    /// Send stream started notification
    func notifyStreamStarted(channelName: String) {
        send(
            type: .streamStarted,
            title: "Now Playing",
            body: channelName,
            subtitle: "Stream started"
        )
    }
    
    /// Send AI fix suggestion notification
    func notifyAIFix(fixCount: Int, actionURL: URL) {
        send(
            type: .aiFix,
            title: "AI Found \(fixCount) Fix\(fixCount > 1 ? "es" : "")",
            body: "Click to review and apply suggested fixes",
            subtitle: "Troubleshooting complete",
            actionURL: actionURL
        )
    }
    
    /// Send update available notification
    func notifyUpdateAvailable(version: String, downloadURL: URL) {
        send(
            type: .update,
            title: "Update Available",
            body: "EXStreamTV \(version) is now available",
            subtitle: "Click to download",
            actionURL: downloadURL
        )
    }
    
    // MARK: - Notification Categories
    
    /// Register notification categories and actions
    func registerCategories() {
        // Server error category with retry action
        let retryAction = UNNotificationAction(
            identifier: "retry",
            title: "Retry",
            options: []
        )
        
        let viewLogsAction = UNNotificationAction(
            identifier: "view_logs",
            title: "View Logs",
            options: [.foreground]
        )
        
        let serverErrorCategory = UNNotificationCategory(
            identifier: EXStreamNotificationType.serverError.rawValue,
            actions: [retryAction, viewLogsAction],
            intentIdentifiers: []
        )
        
        // AI fix category
        let applyFixAction = UNNotificationAction(
            identifier: "apply_fix",
            title: "Apply Fix",
            options: [.foreground]
        )
        
        let dismissAction = UNNotificationAction(
            identifier: "dismiss",
            title: "Dismiss",
            options: []
        )
        
        let aiFixCategory = UNNotificationCategory(
            identifier: EXStreamNotificationType.aiFix.rawValue,
            actions: [applyFixAction, dismissAction],
            intentIdentifiers: []
        )
        
        // Update category
        let downloadAction = UNNotificationAction(
            identifier: "download",
            title: "Download",
            options: [.foreground]
        )
        
        let updateCategory = UNNotificationCategory(
            identifier: EXStreamNotificationType.update.rawValue,
            actions: [downloadAction, dismissAction],
            intentIdentifiers: []
        )
        
        center.setNotificationCategories([
            serverErrorCategory,
            aiFixCategory,
            updateCategory
        ])
    }
    
    // MARK: - Badge Management
    
    /// Update dock badge with stream count
    func updateBadge(streamCount: Int) {
        if streamCount > 0 {
            NSApplication.shared.dockTile.badgeLabel = "\(streamCount)"
        } else {
            NSApplication.shared.dockTile.badgeLabel = nil
        }
    }
    
    /// Clear dock badge
    func clearBadge() {
        NSApplication.shared.dockTile.badgeLabel = nil
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension NotificationManager: UNUserNotificationCenterDelegate {
    
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        // Show notifications even when app is in foreground
        return [.banner, .sound, .badge]
    }
    
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let userInfo = response.notification.request.content.userInfo
        
        // Handle notification tap
        if response.actionIdentifier == UNNotificationDefaultActionIdentifier {
            // Open action URL if provided
            if let urlString = userInfo["actionURL"] as? String,
               let url = URL(string: urlString) {
                await MainActor.run {
                    NSWorkspace.shared.open(url)
                }
            }
            return
        }
        
        // Handle custom actions
        switch response.actionIdentifier {
        case "retry":
            // Post notification to retry server start
            await MainActor.run {
                NotificationCenter.default.post(name: .retryServerStart, object: nil)
            }
            
        case "view_logs":
            // Open logs folder
            await MainActor.run {
                if let logsPath = FileManager.default.urls(
                    for: .libraryDirectory,
                    in: .userDomainMask
                ).first?.appendingPathComponent("Logs/EXStreamTV") {
                    NSWorkspace.shared.open(logsPath)
                }
            }
            
        case "apply_fix":
            // Open fix URL
            if let urlString = userInfo["actionURL"] as? String,
               let url = URL(string: urlString) {
                await MainActor.run {
                    NSWorkspace.shared.open(url)
                }
            }
            
        case "download":
            // Open download URL
            if let urlString = userInfo["actionURL"] as? String,
               let url = URL(string: urlString) {
                await MainActor.run {
                    NSWorkspace.shared.open(url)
                }
            }
            
        default:
            break
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let retryServerStart = Notification.Name("retryServerStart")
}
