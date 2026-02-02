//
//  SettingsView.swift
//  EXStreamTVApp
//
//  Application settings and preferences view.
//

import SwiftUI

struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gear")
                }
            
            ServerSettingsView()
                .tabItem {
                    Label("Server", systemImage: "server.rack")
                }
            
            ShortcutsSettingsView()
                .tabItem {
                    Label("Shortcuts", systemImage: "keyboard")
                }
            
            AISettingsView()
                .environmentObject(AIProviderManager.shared)
                .tabItem {
                    Label("AI", systemImage: "brain")
                }
            
            NotificationSettingsView()
                .tabItem {
                    Label("Notifications", systemImage: "bell")
                }
            
            AdvancedSettingsView()
                .tabItem {
                    Label("Advanced", systemImage: "wrench.and.screwdriver")
                }
        }
        .frame(width: 600, height: 500)
    }
}

// MARK: - General Settings

struct GeneralSettingsView: View {
    @AppStorage("autoStartServer") private var autoStartServer = false
    @AppStorage("restartAfterSleep") private var restartAfterSleep = true
    @AppStorage("launchAtLogin") private var launchAtLogin = false
    
    var body: some View {
        Form {
            Section {
                Toggle("Start server automatically on launch", isOn: $autoStartServer)
                Toggle("Restart server after system wake", isOn: $restartAfterSleep)
                Toggle("Launch at login", isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { _, newValue in
                        updateLaunchAtLogin(enabled: newValue)
                    }
            } header: {
                Text("Startup")
            }
            
            Section {
                HStack {
                    Text("Version")
                    Spacer()
                    Text("1.4.0")
                        .foregroundColor(.secondary)
                }
                
                HStack {
                    Text("Build")
                    Spacer()
                    Text("2026.01.28")
                        .foregroundColor(.secondary)
                }
            } header: {
                Text("About")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
    
    private func updateLaunchAtLogin(enabled: Bool) {
        LoginItemManager.setLaunchAtLogin(enabled: enabled)
    }
}

// MARK: - Server Settings

struct ServerSettingsView: View {
    @AppStorage("serverPort") private var serverPort = 8411
    @AppStorage("pythonPath") private var pythonPath = "/usr/bin/python3"
    @AppStorage("serverPath") private var serverPath = ""
    
    @State private var isValidatingPython = false
    @State private var pythonVersion: String?
    @State private var pythonError: String?
    
    var body: some View {
        Form {
            Section {
                HStack {
                    Text("Port")
                    Spacer()
                    TextField("Port", value: $serverPort, format: .number)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 100)
                }
                
                Text("Default: 8411. Make sure this port is not in use by another application.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } header: {
                Text("Network")
            }
            
            Section {
                HStack {
                    Text("Python Path")
                    Spacer()
                    TextField("Python executable", text: $pythonPath)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 250)
                    
                    Button("Browse") {
                        selectPythonPath()
                    }
                }
                
                if isValidatingPython {
                    HStack {
                        ProgressView()
                            .scaleEffect(0.7)
                        Text("Validating...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } else if let version = pythonVersion {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text("Python \(version)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } else if let error = pythonError {
                    HStack {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.red)
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                }
                
                Button("Validate Python") {
                    validatePython()
                }
            } header: {
                Text("Python")
            }
            
            Section {
                HStack {
                    Text("Server Path")
                    Spacer()
                    TextField("EXStreamTV directory", text: $serverPath)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 250)
                    
                    Button("Browse") {
                        selectServerPath()
                    }
                }
                
                Text("Leave empty to auto-detect from app location.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } header: {
                Text("Server Location")
            }
        }
        .formStyle(.grouped)
        .padding()
        .onAppear {
            validatePython()
        }
    }
    
    private func selectPythonPath() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.directoryURL = URL(fileURLWithPath: "/usr/bin")
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                pythonPath = url.path
                validatePython()
            }
        }
    }
    
    private func selectServerPath() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                serverPath = url.path
            }
        }
    }
    
    private func validatePython() {
        isValidatingPython = true
        pythonVersion = nil
        pythonError = nil
        
        Task {
            do {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: pythonPath)
                process.arguments = ["--version"]
                
                let pipe = Pipe()
                process.standardOutput = pipe
                process.standardError = pipe
                
                try process.run()
                process.waitUntilExit()
                
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                
                await MainActor.run {
                    if process.terminationStatus == 0, let output = output {
                        pythonVersion = output.replacingOccurrences(of: "Python ", with: "")
                    } else {
                        pythonError = "Invalid Python installation"
                    }
                    isValidatingPython = false
                }
            } catch {
                await MainActor.run {
                    pythonError = error.localizedDescription
                    isValidatingPython = false
                }
            }
        }
    }
}

// MARK: - Shortcuts Settings

struct ShortcutsSettingsView: View {
    @ObservedObject private var hotkeyManager = HotkeyManager.shared
    @State private var selectedAction: HotkeyManager.HotkeyAction?
    @State private var isRecording = false
    
    var body: some View {
        Form {
            Section {
                Toggle("Enable global keyboard shortcuts", isOn: $hotkeyManager.isEnabled)
                
                Text("Global shortcuts work even when EXStreamTV is in the background.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } header: {
                Text("General")
            }
            
            Section {
                ForEach(HotkeyManager.HotkeyAction.allCases) { action in
                    HStack {
                        Text(action.displayName)
                        
                        Spacer()
                        
                        if selectedAction == action && isRecording {
                            Text("Press keys...")
                                .foregroundColor(.accentColor)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.accentColor.opacity(0.1))
                                .cornerRadius(4)
                        } else {
                            Button(action: {
                                // For now, just show the current shortcut
                                // A full implementation would capture key presses
                            }) {
                                Text(hotkeyManager.displayString(for: action))
                                    .foregroundColor(.secondary)
                            }
                            .buttonStyle(.bordered)
                        }
                        
                        Button(action: {
                            hotkeyManager.removeHotkey(action)
                        }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.secondary)
                        }
                        .buttonStyle(.plain)
                        .opacity(hotkeyManager.hotkeys[action] != nil ? 1 : 0)
                    }
                    .padding(.vertical, 2)
                }
            } header: {
                Text("Keyboard Shortcuts")
            } footer: {
                Text("Default shortcuts use ⌃⌥ (Control + Option) as modifiers.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Section {
                Button("Reset to Defaults") {
                    hotkeyManager.resetToDefaults()
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        .disabled(!hotkeyManager.isEnabled)
    }
}

// MARK: - Notification Settings

struct NotificationSettingsView: View {
    @AppStorage("showNotifications") private var showNotifications = true
    @AppStorage("notifyOnStart") private var notifyOnStart = true
    @AppStorage("notifyOnStop") private var notifyOnStop = true
    @AppStorage("notifyOnError") private var notifyOnError = true
    @AppStorage("notifyOnStreamStart") private var notifyOnStreamStart = false
    
    var body: some View {
        Form {
            Section {
                Toggle("Enable notifications", isOn: $showNotifications)
            } header: {
                Text("General")
            }
            
            Section {
                Toggle("Server started", isOn: $notifyOnStart)
                    .disabled(!showNotifications)
                Toggle("Server stopped", isOn: $notifyOnStop)
                    .disabled(!showNotifications)
                Toggle("Server errors", isOn: $notifyOnError)
                    .disabled(!showNotifications)
                Toggle("Stream started", isOn: $notifyOnStreamStart)
                    .disabled(!showNotifications)
            } header: {
                Text("Events")
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Advanced Settings

struct AdvancedSettingsView: View {
    @AppStorage("debugMode") private var debugMode = false
    @AppStorage("logLevel") private var logLevel = "INFO"
    @AppStorage("healthCheckInterval") private var healthCheckInterval = 5
    
    @State private var showingResetAlert = false
    
    var body: some View {
        Form {
            Section {
                Toggle("Debug mode", isOn: $debugMode)
                
                Picker("Log level", selection: $logLevel) {
                    Text("Debug").tag("DEBUG")
                    Text("Info").tag("INFO")
                    Text("Warning").tag("WARNING")
                    Text("Error").tag("ERROR")
                }
                .pickerStyle(.menu)
            } header: {
                Text("Logging")
            }
            
            Section {
                HStack {
                    Text("Health check interval")
                    Spacer()
                    Picker("", selection: $healthCheckInterval) {
                        Text("1 second").tag(1)
                        Text("5 seconds").tag(5)
                        Text("10 seconds").tag(10)
                        Text("30 seconds").tag(30)
                    }
                    .pickerStyle(.menu)
                    .frame(width: 150)
                }
            } header: {
                Text("Monitoring")
            }
            
            Section {
                Button("Reset All Settings") {
                    showingResetAlert = true
                }
                .foregroundColor(.red)
                
                Button("Open Logs Folder") {
                    openLogsFolder()
                }
                
                Button("Open Configuration Folder") {
                    openConfigFolder()
                }
            } header: {
                Text("Maintenance")
            }
        }
        .formStyle(.grouped)
        .padding()
        .alert("Reset Settings", isPresented: $showingResetAlert) {
            Button("Cancel", role: .cancel) { }
            Button("Reset", role: .destructive) {
                resetAllSettings()
            }
        } message: {
            Text("This will reset all settings to their default values. This action cannot be undone.")
        }
    }
    
    private func openLogsFolder() {
        let logsPath = FileManager.default.urls(
            for: .libraryDirectory,
            in: .userDomainMask
        ).first?.appendingPathComponent("Logs/EXStreamTV")
        
        if let path = logsPath {
            NSWorkspace.shared.open(path)
        }
    }
    
    private func openConfigFolder() {
        let configPath = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first?.appendingPathComponent("EXStreamTV")
        
        if let path = configPath {
            NSWorkspace.shared.open(path)
        }
    }
    
    private func resetAllSettings() {
        let defaults = UserDefaults.standard
        let dictionary = defaults.dictionaryRepresentation()
        
        for key in dictionary.keys {
            defaults.removeObject(forKey: key)
        }
        
        defaults.synchronize()
        
        // Reset hotkeys to defaults
        HotkeyManager.shared.resetToDefaults()
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environmentObject(ServerManager())
}
