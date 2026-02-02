//
//  EXStreamTVApp.swift
//  EXStreamTVApp
//
//  Main entry point for the EXStreamTV macOS menu bar application.
//  Provides system tray integration, server control, and quick access to features.
//
//  Note: This version uses native NSMenu via StatusBarController instead of
//  SwiftUI MenuBarExtra for a more traditional macOS experience.
//

import SwiftUI

@main
struct EXStreamTVApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        // Settings window
        Settings {
            SettingsView()
                .environmentObject(appDelegate.serverManager)
        }
        
        // Dashboard window
        WindowGroup("EXStreamTV Dashboard", id: "dashboard") {
            DashboardWindowView()
                .environmentObject(appDelegate.serverManager)
                .environmentObject(appDelegate.channelManager)
        }
        .defaultSize(width: 1200, height: 800)
    }
}

// Note: The menu bar is now handled by StatusBarController in AppDelegate
// using native NSStatusItem + NSMenu for a more traditional macOS experience.
// The MenuBarView and MenuBarIcon SwiftUI views are kept for reference but
// are no longer used in the main interface.
