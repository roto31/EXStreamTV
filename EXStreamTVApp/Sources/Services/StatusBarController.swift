//
//  StatusBarController.swift
//  EXStreamTVApp
//
//  Native NSMenu-based status bar controller for a traditional macOS experience.
//

import AppKit
import Combine

/// Manages the native NSStatusItem and NSMenu for the menu bar interface.
@MainActor
class StatusBarController: NSObject {
    // MARK: - Properties
    
    private var statusItem: NSStatusItem
    private var menu: NSMenu
    
    // Menu item references for dynamic updates
    private var serverStatusItem: NSMenuItem!
    private var startServerItem: NSMenuItem!
    private var stopServerItem: NSMenuItem!
    private var restartServerItem: NSMenuItem!
    private var channelsMenuItem: NSMenuItem!
    private var channelsSubmenu: NSMenu!
    private var webUIItem: NSMenuItem!
    private var dashboardItem: NSMenuItem!
    private var viewLogsItem: NSMenuItem!
    
    // Services
    private weak var serverManager: ServerManager?
    private weak var channelManager: ChannelManager?
    private weak var appDelegate: AppDelegate?
    
    // Subscriptions
    private var cancellables = Set<AnyCancellable>()
    
    // Icon controller
    private let iconController = StatusBarIcon()
    
    // MARK: - Initialization
    
    init(serverManager: ServerManager, channelManager: ChannelManager, appDelegate: AppDelegate) {
        self.serverManager = serverManager
        self.channelManager = channelManager
        self.appDelegate = appDelegate
        
        // Create status item
        self.statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        self.menu = NSMenu()
        
        super.init()
        
        setupStatusItem()
        buildMenu()
        setupSubscriptions()
        updateIcon()
    }
    
    // MARK: - Setup
    
    private func setupStatusItem() {
        if let button = statusItem.button {
            button.image = iconController.icon(for: .stopped, activeStreams: 0)
            button.imagePosition = .imageLeft
            button.target = self
            button.action = #selector(statusItemClicked(_:))
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
        
        statusItem.menu = menu
    }
    
    private func buildMenu() {
        menu.removeAllItems()
        menu.delegate = self
        
        // MARK: - Server Status Section
        serverStatusItem = NSMenuItem(title: "Server: Stopped", action: nil, keyEquivalent: "")
        serverStatusItem.isEnabled = false
        serverStatusItem.image = NSImage(systemSymbolName: "circle.fill", accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: 10, weight: .regular))?
            .tinted(with: .gray)
        menu.addItem(serverStatusItem)
        
        menu.addItem(NSMenuItem.separator())
        
        // MARK: - Server Controls Section
        startServerItem = NSMenuItem(title: "Start Server", action: #selector(startServer), keyEquivalent: "s")
        startServerItem.keyEquivalentModifierMask = [.command]
        startServerItem.target = self
        menu.addItem(startServerItem)
        
        stopServerItem = NSMenuItem(title: "Stop Server", action: #selector(stopServer), keyEquivalent: ".")
        stopServerItem.keyEquivalentModifierMask = [.command]
        stopServerItem.target = self
        stopServerItem.isHidden = true
        menu.addItem(stopServerItem)
        
        restartServerItem = NSMenuItem(title: "Restart Server", action: #selector(restartServer), keyEquivalent: "r")
        restartServerItem.keyEquivalentModifierMask = [.command]
        restartServerItem.target = self
        restartServerItem.isHidden = true
        menu.addItem(restartServerItem)
        
        menu.addItem(NSMenuItem.separator())
        
        // MARK: - Channels Section
        channelsSubmenu = NSMenu()
        channelsMenuItem = NSMenuItem(title: "Channels", action: nil, keyEquivalent: "")
        channelsMenuItem.submenu = channelsSubmenu
        menu.addItem(channelsMenuItem)
        
        menu.addItem(NSMenuItem.separator())
        
        // MARK: - Quick Actions Section
        webUIItem = NSMenuItem(title: "Open Web UI", action: #selector(openWebUI), keyEquivalent: "o")
        webUIItem.keyEquivalentModifierMask = [.command]
        webUIItem.target = self
        menu.addItem(webUIItem)
        
        dashboardItem = NSMenuItem(title: "Open Dashboard", action: #selector(openDashboard), keyEquivalent: "d")
        dashboardItem.keyEquivalentModifierMask = [.command]
        dashboardItem.target = self
        menu.addItem(dashboardItem)
        
        viewLogsItem = NSMenuItem(title: "View Logs", action: #selector(viewLogs), keyEquivalent: "l")
        viewLogsItem.keyEquivalentModifierMask = [.command]
        viewLogsItem.target = self
        menu.addItem(viewLogsItem)
        
        menu.addItem(NSMenuItem.separator())
        
        // MARK: - Settings Section
        let settingsItem = NSMenuItem(title: "Settings...", action: #selector(openSettings), keyEquivalent: ",")
        settingsItem.keyEquivalentModifierMask = [.command]
        settingsItem.target = self
        menu.addItem(settingsItem)
        
        let aboutItem = NSMenuItem(title: "About EXStreamTV", action: #selector(showAbout), keyEquivalent: "")
        aboutItem.target = self
        menu.addItem(aboutItem)
        
        menu.addItem(NSMenuItem.separator())
        
        // MARK: - Quit Section
        let quitItem = NSMenuItem(title: "Quit EXStreamTV", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.keyEquivalentModifierMask = [.command]
        quitItem.target = self
        menu.addItem(quitItem)
        
        // Initial state update
        updateMenuState()
    }
    
    private func setupSubscriptions() {
        guard let serverManager = serverManager else { return }
        
        // Subscribe to server state changes
        Publishers.CombineLatest4(
            serverManager.$isRunning,
            serverManager.$isStarting,
            serverManager.$isStopping,
            serverManager.$activeStreams
        )
        .receive(on: DispatchQueue.main)
        .sink { [weak self] isRunning, isStarting, isStopping, activeStreams in
            self?.updateMenuState()
            self?.updateIcon()
        }
        .store(in: &cancellables)
        
        // Subscribe to channel changes
        channelManager?.$channels
            .receive(on: DispatchQueue.main)
            .sink { [weak self] channels in
                self?.updateChannelsSubmenu(channels)
            }
            .store(in: &cancellables)
        
        channelManager?.$activeChannels
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.updateMenuState()
            }
            .store(in: &cancellables)
    }
    
    // MARK: - State Updates
    
    private func updateMenuState() {
        guard let serverManager = serverManager else { return }
        
        let isRunning = serverManager.isRunning
        let isStarting = serverManager.isStarting
        let isStopping = serverManager.isStopping
        let isTransitioning = isStarting || isStopping
        
        // Update status item
        if isStarting {
            serverStatusItem.title = "Server: Starting..."
            serverStatusItem.image = statusDot(color: .systemYellow)
        } else if isStopping {
            serverStatusItem.title = "Server: Stopping..."
            serverStatusItem.image = statusDot(color: .systemYellow)
        } else if isRunning {
            let uptimeText = serverManager.formattedUptime
            serverStatusItem.title = "Server: Running (\(uptimeText))"
            serverStatusItem.image = statusDot(color: .systemGreen)
        } else {
            serverStatusItem.title = "Server: Stopped"
            serverStatusItem.image = statusDot(color: .gray)
        }
        
        // Update control items visibility and state
        startServerItem.isHidden = isRunning || isTransitioning
        stopServerItem.isHidden = !isRunning || isTransitioning
        restartServerItem.isHidden = !isRunning || isTransitioning
        
        // Disable actions during transitions
        startServerItem.isEnabled = !isTransitioning
        stopServerItem.isEnabled = !isTransitioning
        restartServerItem.isEnabled = !isTransitioning
        
        // Update quick actions state
        webUIItem.isEnabled = isRunning
        dashboardItem.isEnabled = isRunning
        viewLogsItem.isEnabled = isRunning
        channelsMenuItem.isEnabled = isRunning
    }
    
    private func updateIcon() {
        guard let serverManager = serverManager, let button = statusItem.button else { return }
        
        let state: StatusBarIcon.State
        if serverManager.isStarting {
            state = .starting
        } else if serverManager.isStopping {
            state = .stopping
        } else if serverManager.isRunning {
            if serverManager.lastError != nil {
                state = .error
            } else {
                state = .running
            }
        } else {
            state = .stopped
        }
        
        button.image = iconController.icon(for: state, activeStreams: serverManager.activeStreams)
    }
    
    private func updateChannelsSubmenu(_ channels: [Channel]) {
        channelsSubmenu.removeAllItems()
        
        if channels.isEmpty {
            let noChannelsItem = NSMenuItem(title: "No channels available", action: nil, keyEquivalent: "")
            noChannelsItem.isEnabled = false
            channelsSubmenu.addItem(noChannelsItem)
            return
        }
        
        // Group channels by group
        let groupedChannels = Dictionary(grouping: channels.filter { $0.isEnabled }) { $0.group ?? "Uncategorized" }
        let sortedGroups = groupedChannels.keys.sorted()
        
        for (index, group) in sortedGroups.enumerated() {
            if index > 0 {
                channelsSubmenu.addItem(NSMenuItem.separator())
            }
            
            // Group header
            let groupHeader = NSMenuItem(title: group, action: nil, keyEquivalent: "")
            groupHeader.isEnabled = false
            let attributes: [NSAttributedString.Key: Any] = [
                .font: NSFont.systemFont(ofSize: 11, weight: .semibold),
                .foregroundColor: NSColor.secondaryLabelColor
            ]
            groupHeader.attributedTitle = NSAttributedString(string: group.uppercased(), attributes: attributes)
            channelsSubmenu.addItem(groupHeader)
            
            // Channels in group
            if let groupChannels = groupedChannels[group]?.sorted(by: { $0.number < $1.number }) {
                for channel in groupChannels {
                    let channelItem = NSMenuItem(
                        title: "\(channel.number). \(channel.name)",
                        action: #selector(openChannelStream(_:)),
                        keyEquivalent: ""
                    )
                    channelItem.target = self
                    channelItem.tag = channel.id
                    
                    // Mark active channels
                    if channelManager?.activeChannels.contains(where: { $0.id == channel.id }) == true {
                        channelItem.image = NSImage(systemSymbolName: "play.circle.fill", accessibilityDescription: nil)?
                            .withSymbolConfiguration(.init(pointSize: 12, weight: .regular))?
                            .tinted(with: .systemGreen)
                    }
                    
                    channelsSubmenu.addItem(channelItem)
                }
            }
        }
        
        // Add separator and view all option
        channelsSubmenu.addItem(NSMenuItem.separator())
        let viewAllItem = NSMenuItem(title: "View All Channels...", action: #selector(openChannelsPage), keyEquivalent: "")
        viewAllItem.target = self
        channelsSubmenu.addItem(viewAllItem)
    }
    
    private func statusDot(color: NSColor) -> NSImage? {
        NSImage(systemSymbolName: "circle.fill", accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: 8, weight: .regular))?
            .tinted(with: color)
    }
    
    // MARK: - Actions
    
    @objc private func statusItemClicked(_ sender: NSStatusBarButton) {
        // Both left and right click show the menu
        statusItem.menu = menu
        statusItem.button?.performClick(nil)
    }
    
    @objc private func startServer() {
        Task {
            await serverManager?.start()
        }
    }
    
    @objc private func stopServer() {
        Task {
            await serverManager?.stop()
        }
    }
    
    @objc private func restartServer() {
        Task {
            await serverManager?.restart()
        }
    }
    
    @objc private func openWebUI() {
        appDelegate?.openWebUI()
    }
    
    @objc private func openDashboard() {
        appDelegate?.openDashboard()
    }
    
    @objc private func viewLogs() {
        guard let serverManager = serverManager else { return }
        let port = serverManager.port
        if let url = URL(string: "http://localhost:\(port)/logs") {
            NSWorkspace.shared.open(url)
        }
    }
    
    @objc private func openChannelStream(_ sender: NSMenuItem) {
        let channelId = sender.tag
        channelManager?.openChannelStream(channelId)
    }
    
    @objc private func openChannelsPage() {
        guard let serverManager = serverManager else { return }
        let port = serverManager.port
        if let url = URL(string: "http://localhost:\(port)/channels") {
            NSWorkspace.shared.open(url)
        }
    }
    
    @objc private func openSettings() {
        NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    @objc private func showAbout() {
        appDelegate?.showAboutWindow()
    }
    
    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }
    
    // MARK: - Public Methods
    
    /// Force refresh the menu state
    func refreshMenu() {
        updateMenuState()
        Task {
            await channelManager?.refresh()
        }
    }
}

// MARK: - NSMenuDelegate

extension StatusBarController: NSMenuDelegate {
    func menuWillOpen(_ menu: NSMenu) {
        // Refresh state when menu opens
        updateMenuState()
    }
    
    func menuNeedsUpdate(_ menu: NSMenu) {
        // Update channels when menu is about to be displayed
        if let channels = channelManager?.channels {
            updateChannelsSubmenu(channels)
        }
    }
}

// MARK: - NSImage Extension

private extension NSImage {
    func tinted(with color: NSColor) -> NSImage {
        let image = self.copy() as! NSImage
        image.lockFocus()
        color.set()
        let imageRect = NSRect(origin: .zero, size: image.size)
        imageRect.fill(using: .sourceAtop)
        image.unlockFocus()
        image.isTemplate = false
        return image
    }
}
