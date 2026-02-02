//
//  TouchBarController.swift
//  EXStreamTVApp
//
//  Touch Bar support for MacBooks with Touch Bar.
//

import AppKit
import Combine

// MARK: - Touch Bar Item Identifiers

@available(macOS 10.12.2, *)
extension NSTouchBarItem.Identifier {
    static let serverStatus = NSTouchBarItem.Identifier("com.exstreamtv.touchbar.serverStatus")
    static let startStop = NSTouchBarItem.Identifier("com.exstreamtv.touchbar.startStop")
    static let restart = NSTouchBarItem.Identifier("com.exstreamtv.touchbar.restart")
    static let openWebUI = NSTouchBarItem.Identifier("com.exstreamtv.touchbar.openWebUI")
    static let channels = NSTouchBarItem.Identifier("com.exstreamtv.touchbar.channels")
}

// MARK: - Touch Bar Controller

/// Manages Touch Bar integration for the EXStreamTV app.
@available(macOS 10.12.2, *)
@MainActor
class TouchBarController: NSObject {
    // MARK: - Properties
    
    private weak var serverManager: ServerManager?
    private weak var channelManager: ChannelManager?
    private weak var appDelegate: AppDelegate?
    
    private var touchBar: NSTouchBar?
    private var cancellables = Set<AnyCancellable>()
    
    // Touch bar items
    private var serverStatusItem: NSCustomTouchBarItem?
    private var startStopItem: NSCustomTouchBarItem?
    
    // MARK: - Initialization
    
    init(serverManager: ServerManager, channelManager: ChannelManager, appDelegate: AppDelegate) {
        self.serverManager = serverManager
        self.channelManager = channelManager
        self.appDelegate = appDelegate
        
        super.init()
        
        setupSubscriptions()
    }
    
    // MARK: - Public Methods
    
    /// Creates and returns a configured Touch Bar
    func makeTouchBar() -> NSTouchBar {
        let touchBar = NSTouchBar()
        touchBar.delegate = self
        touchBar.defaultItemIdentifiers = [
            .serverStatus,
            .startStop,
            .restart,
            .flexibleSpace,
            .openWebUI
        ]
        
        self.touchBar = touchBar
        return touchBar
    }
    
    /// Updates Touch Bar items based on current state
    func updateTouchBar() {
        guard let serverManager = serverManager else { return }
        
        // Update server status
        if let statusItem = serverStatusItem?.view as? NSButton {
            updateServerStatusButton(statusItem, with: serverManager)
        }
        
        // Update start/stop button
        if let startStopButton = startStopItem?.view as? NSButton {
            updateStartStopButton(startStopButton, with: serverManager)
        }
    }
    
    // MARK: - Private Methods
    
    private func setupSubscriptions() {
        guard let serverManager = serverManager else { return }
        
        Publishers.CombineLatest4(
            serverManager.$isRunning,
            serverManager.$isStarting,
            serverManager.$isStopping,
            serverManager.$activeStreams
        )
        .receive(on: DispatchQueue.main)
        .sink { [weak self] _, _, _, _ in
            self?.updateTouchBar()
        }
        .store(in: &cancellables)
    }
    
    private func updateServerStatusButton(_ button: NSButton, with serverManager: ServerManager) {
        let statusColor: NSColor
        let statusText: String
        
        if serverManager.isStarting {
            statusColor = .systemYellow
            statusText = "Starting..."
        } else if serverManager.isStopping {
            statusColor = .systemYellow
            statusText = "Stopping..."
        } else if serverManager.isRunning {
            statusColor = .systemGreen
            let streams = serverManager.activeStreams
            statusText = streams > 0 ? "Running (\(streams))" : "Running"
        } else {
            statusColor = .systemGray
            statusText = "Stopped"
        }
        
        button.title = statusText
        button.image = NSImage(systemSymbolName: "circle.fill", accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: 10, weight: .regular))
        button.imagePosition = .imageLeading
        button.contentTintColor = statusColor
    }
    
    private func updateStartStopButton(_ button: NSButton, with serverManager: ServerManager) {
        let isTransitioning = serverManager.isStarting || serverManager.isStopping
        
        if serverManager.isRunning {
            button.title = "Stop"
            button.image = NSImage(systemSymbolName: "stop.fill", accessibilityDescription: nil)
            button.bezelColor = .systemRed
        } else {
            button.title = "Start"
            button.image = NSImage(systemSymbolName: "play.fill", accessibilityDescription: nil)
            button.bezelColor = .systemGreen
        }
        
        button.isEnabled = !isTransitioning
    }
    
    // MARK: - Actions
    
    @objc private func toggleServer() {
        Task {
            if serverManager?.isRunning == true {
                await serverManager?.stop()
            } else {
                await serverManager?.start()
            }
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
}

// MARK: - NSTouchBarDelegate

@available(macOS 10.12.2, *)
extension TouchBarController: NSTouchBarDelegate {
    func touchBar(_ touchBar: NSTouchBar, makeItemForIdentifier identifier: NSTouchBarItem.Identifier) -> NSTouchBarItem? {
        switch identifier {
        case .serverStatus:
            let item = NSCustomTouchBarItem(identifier: identifier)
            let button = NSButton(title: "Stopped", image: NSImage(), target: nil, action: nil)
            button.imagePosition = .imageLeading
            button.isEnabled = false
            item.view = button
            serverStatusItem = item
            
            if let serverManager = serverManager {
                updateServerStatusButton(button, with: serverManager)
            }
            
            return item
            
        case .startStop:
            let item = NSCustomTouchBarItem(identifier: identifier)
            let button = NSButton(
                title: "Start",
                image: NSImage(systemSymbolName: "play.fill", accessibilityDescription: nil) ?? NSImage(),
                target: self,
                action: #selector(toggleServer)
            )
            button.imagePosition = .imageLeading
            button.bezelColor = .systemGreen
            item.view = button
            startStopItem = item
            
            if let serverManager = serverManager {
                updateStartStopButton(button, with: serverManager)
            }
            
            return item
            
        case .restart:
            let item = NSCustomTouchBarItem(identifier: identifier)
            let button = NSButton(
                title: "Restart",
                image: NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: nil) ?? NSImage(),
                target: self,
                action: #selector(restartServer)
            )
            button.imagePosition = .imageLeading
            item.view = button
            return item
            
        case .openWebUI:
            let item = NSCustomTouchBarItem(identifier: identifier)
            let button = NSButton(
                title: "Web UI",
                image: NSImage(systemSymbolName: "globe", accessibilityDescription: nil) ?? NSImage(),
                target: self,
                action: #selector(openWebUI)
            )
            button.imagePosition = .imageLeading
            button.bezelColor = .systemBlue
            item.view = button
            return item
            
        default:
            return nil
        }
    }
}

// MARK: - Touch Bar Provider Protocol

/// Protocol for views that can provide a Touch Bar
@available(macOS 10.12.2, *)
protocol TouchBarProvider {
    var touchBarController: TouchBarController? { get }
}
