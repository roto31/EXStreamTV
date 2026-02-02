//
//  AppDelegate.swift
//  EXStreamTVApp
//
//  Application delegate handling lifecycle events and managing services.
//

import AppKit
import Combine
import SwiftUI

class AppDelegate: NSObject, NSApplicationDelegate {
    // MARK: - Properties
    
    let serverManager = ServerManager()
    let channelManager = ChannelManager()
    
    // Native menu bar controller
    private var statusBarController: StatusBarController?
    
    // Touch Bar controller
    @available(macOS 10.12.2, *)
    private lazy var touchBarController: TouchBarController = {
        TouchBarController(serverManager: serverManager, channelManager: channelManager, appDelegate: self)
    }()
    
    // Hotkey manager
    private let hotkeyManager = HotkeyManager.shared
    
    private var aboutWindow: NSWindow?
    private var onboardingWindow: NSWindow?
    
    // MARK: - Lifecycle
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure app behavior
        NSApp.setActivationPolicy(.accessory)
        
        // Load saved preferences
        loadPreferences()
        
        // Initialize native status bar controller
        statusBarController = StatusBarController(
            serverManager: serverManager,
            channelManager: channelManager,
            appDelegate: self
        )
        
        // Setup global hotkeys
        setupHotkeys()
        
        // Show onboarding on first run
        if shouldShowOnboarding() {
            showOnboardingWindow()
        } else {
            // Auto-start server if enabled
            if UserDefaults.standard.bool(forKey: "autoStartServer") {
                Task {
                    await serverManager.start()
                }
            }
        }
        
        // Start monitoring
        serverManager.startMonitoring()
        
        // Register for system events
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(handleWake),
            name: NSWorkspace.didWakeNotification,
            object: nil
        )
        
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(handleSleep),
            name: NSWorkspace.willSleepNotification,
            object: nil
        )
        
        print("EXStreamTV Menu Bar App started")
    }
    
    func applicationWillTerminate(_ notification: Notification) {
        // Unregister hotkeys
        hotkeyManager.unregisterAllHotkeys()
        
        // Stop server gracefully
        Task {
            await serverManager.stop()
        }
        
        // Save preferences
        savePreferences()
        
        print("EXStreamTV Menu Bar App terminated")
    }
    
    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
        return true
    }
    
    // MARK: - Dock Menu
    
    func applicationDockMenu(_ sender: NSApplication) -> NSMenu? {
        let dockMenu = NSMenu()
        
        // Server status
        let statusItem = NSMenuItem(title: "Server: \(serverManager.statusText)", action: nil, keyEquivalent: "")
        statusItem.isEnabled = false
        dockMenu.addItem(statusItem)
        
        dockMenu.addItem(NSMenuItem.separator())
        
        // Server controls
        if serverManager.isRunning {
            let stopItem = NSMenuItem(title: "Stop Server", action: #selector(stopServer), keyEquivalent: "")
            stopItem.target = self
            dockMenu.addItem(stopItem)
            
            let restartItem = NSMenuItem(title: "Restart Server", action: #selector(restartServer), keyEquivalent: "")
            restartItem.target = self
            dockMenu.addItem(restartItem)
        } else {
            let startItem = NSMenuItem(title: "Start Server", action: #selector(startServer), keyEquivalent: "")
            startItem.target = self
            dockMenu.addItem(startItem)
        }
        
        dockMenu.addItem(NSMenuItem.separator())
        
        // Quick actions
        let webUIItem = NSMenuItem(title: "Open Web UI", action: #selector(openWebUIAction), keyEquivalent: "")
        webUIItem.target = self
        webUIItem.isEnabled = serverManager.isRunning
        dockMenu.addItem(webUIItem)
        
        let dashboardItem = NSMenuItem(title: "Open Dashboard", action: #selector(openDashboardAction), keyEquivalent: "")
        dashboardItem.target = self
        dashboardItem.isEnabled = serverManager.isRunning
        dockMenu.addItem(dashboardItem)
        
        return dockMenu
    }
    
    // MARK: - System Events
    
    @objc private func handleWake() {
        print("System woke from sleep")
        
        // Restart server if it was running
        if UserDefaults.standard.bool(forKey: "restartAfterSleep") && 
           UserDefaults.standard.bool(forKey: "serverWasRunning") {
            Task {
                await serverManager.start()
            }
        }
    }
    
    @objc private func handleSleep() {
        print("System going to sleep")
        
        // Remember server state
        UserDefaults.standard.set(serverManager.isRunning, forKey: "serverWasRunning")
        
        // Stop server before sleep
        if serverManager.isRunning {
            Task {
                await serverManager.stop()
            }
        }
    }
    
    // MARK: - Hotkey Setup
    
    private func setupHotkeys() {
        hotkeyManager.onStartServer = { [weak self] in
            Task { @MainActor in
                await self?.serverManager.start()
            }
        }
        
        hotkeyManager.onStopServer = { [weak self] in
            Task { @MainActor in
                await self?.serverManager.stop()
            }
        }
        
        hotkeyManager.onRestartServer = { [weak self] in
            Task { @MainActor in
                await self?.serverManager.restart()
            }
        }
        
        hotkeyManager.onOpenWebUI = { [weak self] in
            DispatchQueue.main.async {
                self?.openWebUI()
            }
        }
        
        hotkeyManager.onOpenDashboard = { [weak self] in
            DispatchQueue.main.async {
                self?.openDashboard()
            }
        }
        
        hotkeyManager.onToggleMenu = { [weak self] in
            // Activate the app and show menu
            DispatchQueue.main.async {
                NSApp.activate(ignoringOtherApps: true)
                self?.statusBarController?.refreshMenu()
            }
        }
        
        // Register hotkeys
        hotkeyManager.registerAllHotkeys()
    }
    
    // MARK: - Preferences
    
    private func loadPreferences() {
        // Register defaults
        UserDefaults.standard.register(defaults: [
            "autoStartServer": false,
            "restartAfterSleep": true,
            "serverPort": 8411,
            "showNotifications": true,
            "pythonPath": "/usr/bin/python3",
            "serverPath": "",
            "hotkeysEnabled": true
        ])
    }
    
    private func savePreferences() {
        UserDefaults.standard.synchronize()
    }
    
    // MARK: - Server Actions
    
    @objc private func startServer() {
        Task {
            await serverManager.start()
        }
    }
    
    @objc private func stopServer() {
        Task {
            await serverManager.stop()
        }
    }
    
    @objc private func restartServer() {
        Task {
            await serverManager.restart()
        }
    }
    
    @objc private func openWebUIAction() {
        openWebUI()
    }
    
    @objc private func openDashboardAction() {
        openDashboard()
    }
    
    // MARK: - Public Actions
    
    func showAboutWindow() {
        if aboutWindow == nil {
            let aboutView = AboutView()
            let hostingController = NSHostingController(rootView: aboutView)
            
            aboutWindow = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 400, height: 300),
                styleMask: [.titled, .closable],
                backing: .buffered,
                defer: false
            )
            aboutWindow?.title = "About EXStreamTV"
            aboutWindow?.contentViewController = hostingController
            aboutWindow?.center()
            aboutWindow?.isReleasedWhenClosed = false
        }
        
        aboutWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    func openWebUI() {
        let port = UserDefaults.standard.integer(forKey: "serverPort")
        let url = URL(string: "http://localhost:\(port)")!
        NSWorkspace.shared.open(url)
    }
    
    func openDashboard() {
        if let url = URL(string: "exstreamtv://dashboard") {
            NSWorkspace.shared.open(url)
        }
    }
    
    // MARK: - Touch Bar
    
    @available(macOS 10.12.2, *)
    func getTouchBar() -> NSTouchBar {
        return touchBarController.makeTouchBar()
    }
    
    // MARK: - Onboarding
    
    private func shouldShowOnboarding() -> Bool {
        return !UserDefaults.standard.bool(forKey: "onboarding.complete")
    }
    
    func showOnboardingWindow() {
        if onboardingWindow == nil {
            let onboardingView = OnboardingWizard()
            let hostingController = NSHostingController(rootView: onboardingView)
            
            onboardingWindow = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 700, height: 600),
                styleMask: [.titled, .closable, .miniaturizable],
                backing: .buffered,
                defer: false
            )
            onboardingWindow?.title = "Welcome to EXStreamTV"
            onboardingWindow?.contentViewController = hostingController
            onboardingWindow?.center()
            onboardingWindow?.isReleasedWhenClosed = false
            
            // Make app regular (not accessory) while onboarding is shown
            NSApp.setActivationPolicy(.regular)
        }
        
        onboardingWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        
        // Observe onboarding completion
        OnboardingState.shared.$isOnboardingComplete
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isComplete in
                if isComplete {
                    self?.onboardingDidComplete()
                }
            }
            .store(in: &cancellables)
    }
    
    private func onboardingDidComplete() {
        // Close onboarding window
        onboardingWindow?.close()
        onboardingWindow = nil
        
        // Switch back to accessory mode
        NSApp.setActivationPolicy(.accessory)
        
        // Auto-start server after onboarding
        Task {
            await serverManager.start()
        }
    }
    
    // MARK: - Combine Subscriptions
    
    private var cancellables = Set<AnyCancellable>()
}

// MARK: - Services Integration

extension AppDelegate {
    /// Handles IPTV URL from Services menu
    @objc func handleIPTVURL(_ pboard: NSPasteboard, userData: String?, error: AutoreleasingUnsafeMutablePointer<NSString?>?) {
        guard let items = pboard.pasteboardItems else { return }
        
        for item in items {
            if let urlString = item.string(forType: .string),
               let url = URL(string: urlString) {
                // Handle the IPTV URL - could add to playlist or start streaming
                print("Received IPTV URL from Services: \(url)")
                
                // Open in web UI for now
                let port = UserDefaults.standard.integer(forKey: "serverPort")
                if let addURL = URL(string: "http://localhost:\(port)/playlists?add=\(urlString.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")") {
                    NSWorkspace.shared.open(addURL)
                }
            }
        }
    }
}
