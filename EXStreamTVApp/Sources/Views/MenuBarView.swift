//
//  MenuBarView.swift
//  EXStreamTVApp
//
//  Main menu bar popover view with server controls and quick access.
//

import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var serverManager: ServerManager
    @EnvironmentObject var channelManager: ChannelManager
    @Environment(\.openSettings) private var openSettings
    @Environment(\.openWindow) private var openWindow
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HeaderSection()
            
            Divider()
            
            // Server Status
            ServerStatusSection()
            
            Divider()
            
            // Active Streams
            if serverManager.isRunning {
                ActiveStreamsSection()
                Divider()
            }
            
            // Quick Actions
            QuickActionsSection()
            
            Divider()
            
            // Footer
            FooterSection()
        }
        .frame(width: 320)
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// MARK: - Header Section

struct HeaderSection: View {
    var body: some View {
        HStack {
            Image(systemName: "tv.fill")
                .font(.title2)
                .foregroundColor(.accentColor)
            
            VStack(alignment: .leading, spacing: 2) {
                Text("EXStreamTV")
                    .font(.headline)
                Text("IPTV Streaming Platform")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding()
    }
}

// MARK: - Server Status Section

struct ServerStatusSection: View {
    @EnvironmentObject var serverManager: ServerManager
    
    var body: some View {
        VStack(spacing: 12) {
            // Status row
            HStack {
                Circle()
                    .fill(statusColor)
                    .frame(width: 10, height: 10)
                
                Text("Server")
                    .font(.subheadline)
                
                Spacer()
                
                Text(serverManager.statusText)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            // Control buttons
            HStack(spacing: 12) {
                if serverManager.isRunning {
                    Button(action: {
                        Task { await serverManager.stop() }
                    }) {
                        Label("Stop", systemImage: "stop.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(serverManager.isStopping)
                    
                    Button(action: {
                        Task { await serverManager.restart() }
                    }) {
                        Label("Restart", systemImage: "arrow.clockwise")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(serverManager.isStopping)
                } else {
                    Button(action: {
                        Task { await serverManager.start() }
                    }) {
                        Label("Start Server", systemImage: "play.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(serverManager.isStarting)
                }
            }
            
            // Stats when running
            if serverManager.isRunning {
                HStack(spacing: 16) {
                    StatBadge(
                        icon: "clock",
                        value: serverManager.formattedUptime,
                        label: "Uptime"
                    )
                    
                    StatBadge(
                        icon: "play.tv",
                        value: "\(serverManager.activeStreams)",
                        label: "Streams"
                    )
                    
                    Spacer()
                }
            }
            
            // Error message
            if let error = serverManager.lastError {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .lineLimit(2)
                }
                .padding(8)
                .background(Color.red.opacity(0.1))
                .cornerRadius(6)
            }
        }
        .padding()
    }
    
    private var statusColor: Color {
        if serverManager.isStarting || serverManager.isStopping {
            return .yellow
        }
        return serverManager.isRunning ? .green : .gray
    }
}

// MARK: - Active Streams Section

struct ActiveStreamsSection: View {
    @EnvironmentObject var channelManager: ChannelManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Active Streams")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Spacer()
                
                if channelManager.isLoading {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }
            
            if channelManager.activeChannels.isEmpty {
                Text("No active streams")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 8)
            } else {
                ForEach(channelManager.activeChannels) { channel in
                    ChannelRow(channel: channel)
                }
            }
        }
        .padding()
        .onAppear {
            Task { await channelManager.refresh() }
        }
    }
}

struct ChannelRow: View {
    let channel: Channel
    @EnvironmentObject var channelManager: ChannelManager
    
    var body: some View {
        HStack {
            Circle()
                .fill(.green)
                .frame(width: 8, height: 8)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(channel.displayName)
                    .font(.caption)
                    .fontWeight(.medium)
                
                if let group = channel.group {
                    Text(group)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            Button(action: {
                channelManager.openChannelStream(channel.id)
            }) {
                Image(systemName: "play.circle")
            }
            .buttonStyle(.plain)
            .help("Open stream")
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Quick Actions Section

struct QuickActionsSection: View {
    @EnvironmentObject var serverManager: ServerManager
    @Environment(\.openWindow) private var openWindow
    
    var body: some View {
        VStack(spacing: 8) {
            QuickActionButton(
                title: "Open Web UI",
                icon: "globe",
                action: openWebUI
            )
            .disabled(!serverManager.isRunning)
            
            QuickActionButton(
                title: "Open Dashboard",
                icon: "rectangle.3.group",
                action: { openWindow(id: "dashboard") }
            )
            .disabled(!serverManager.isRunning)
            
            QuickActionButton(
                title: "View Channels",
                icon: "tv",
                action: openChannels
            )
            .disabled(!serverManager.isRunning)
            
            QuickActionButton(
                title: "View Logs",
                icon: "doc.text",
                action: openLogs
            )
            .disabled(!serverManager.isRunning)
        }
        .padding()
    }
    
    private func openWebUI() {
        let port = serverManager.port
        if let url = URL(string: "http://localhost:\(port)") {
            NSWorkspace.shared.open(url)
        }
    }
    
    private func openChannels() {
        let port = serverManager.port
        if let url = URL(string: "http://localhost:\(port)/channels") {
            NSWorkspace.shared.open(url)
        }
    }
    
    private func openLogs() {
        let port = serverManager.port
        if let url = URL(string: "http://localhost:\(port)/logs") {
            NSWorkspace.shared.open(url)
        }
    }
}

struct QuickActionButton: View {
    let title: String
    let icon: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Image(systemName: icon)
                    .frame(width: 20)
                Text(title)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .buttonStyle(.plain)
        .padding(.vertical, 4)
    }
}

// MARK: - Footer Section

struct FooterSection: View {
    @Environment(\.openSettings) private var openSettings
    
    var body: some View {
        HStack {
            Button(action: { openSettings() }) {
                Label("Settings", systemImage: "gear")
            }
            .buttonStyle(.plain)
            
            Spacer()
            
            Button(action: { NSApplication.shared.terminate(nil) }) {
                Label("Quit", systemImage: "power")
            }
            .buttonStyle(.plain)
        }
        .font(.subheadline)
        .padding()
    }
}

// MARK: - Supporting Views

struct StatBadge: View {
    let icon: String
    let value: String
    let label: String
    
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundColor(.secondary)
                .font(.caption)
            
            VStack(alignment: .leading, spacing: 0) {
                Text(value)
                    .font(.caption)
                    .fontWeight(.medium)
                Text(label)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Preview

#Preview {
    MenuBarView()
        .environmentObject(ServerManager())
        .environmentObject(ChannelManager())
}
