//
//  ChannelSwitcher.swift
//  EXStreamTVApp
//
//  Channel switcher overlay with keyboard shortcuts.
//

import SwiftUI

struct ChannelSwitcher: View {
    @EnvironmentObject var channelManager: ChannelManager
    @Binding var isPresented: Bool
    @Binding var currentChannelIndex: Int
    
    @State private var typedNumber = ""
    @State private var clearNumberTask: Task<Void, Never>?
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Channels")
                    .font(.headline)
                
                Spacer()
                
                if !typedNumber.isEmpty {
                    Text("Go to: \(typedNumber)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Capsule().fill(.ultraThinMaterial))
                }
                
                Button {
                    isPresented = false
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()
            .background(.ultraThinMaterial)
            
            // Channel list
            ScrollViewReader { proxy in
                List(selection: Binding(
                    get: { channelManager.channels.indices.contains(currentChannelIndex) ? channelManager.channels[currentChannelIndex].id : nil },
                    set: { newId in
                        if let id = newId, let index = channelManager.channels.firstIndex(where: { $0.id == id }) {
                            selectChannel(at: index)
                        }
                    }
                )) {
                    ForEach(Array(channelManager.channels.enumerated()), id: \.element.id) { index, channel in
                        ChannelRow(
                            channel: channel,
                            number: index + 1,
                            isSelected: index == currentChannelIndex,
                            isPlaying: channelManager.playingChannelId == channel.id
                        )
                        .tag(channel.id)
                        .id(channel.id)
                        .onTapGesture {
                            selectChannel(at: index)
                        }
                    }
                }
                .listStyle(.plain)
                .onChange(of: currentChannelIndex) { _, newIndex in
                    if channelManager.channels.indices.contains(newIndex) {
                        withAnimation {
                            proxy.scrollTo(channelManager.channels[newIndex].id, anchor: .center)
                        }
                    }
                }
            }
            
            // Footer with keyboard shortcuts
            HStack(spacing: 16) {
                KeyboardShortcutHint(key: "↑↓", description: "Navigate")
                KeyboardShortcutHint(key: "↵", description: "Select")
                KeyboardShortcutHint(key: "0-9", description: "Jump to channel")
                KeyboardShortcutHint(key: "ESC", description: "Close")
            }
            .font(.caption2)
            .padding(8)
            .background(.ultraThinMaterial)
        }
        .frame(width: 320, height: 400)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(radius: 20)
        .onKeyPress { press in
            handleKeyPress(press)
        }
    }
    
    private func selectChannel(at index: Int) {
        currentChannelIndex = index
        if channelManager.channels.indices.contains(index) {
            channelManager.selectChannel(channelManager.channels[index])
        }
        
        // Close after brief delay
        Task {
            try? await Task.sleep(nanoseconds: 200_000_000)
            isPresented = false
        }
    }
    
    private func handleKeyPress(_ press: KeyPress) -> KeyPress.Result {
        switch press.key {
        case .upArrow:
            navigateUp()
            return .handled
        case .downArrow:
            navigateDown()
            return .handled
        case .return, .space:
            selectChannel(at: currentChannelIndex)
            return .handled
        case .escape:
            isPresented = false
            return .handled
        default:
            // Handle number input
            if let char = press.characters.first, char.isNumber {
                handleNumberInput(String(char))
                return .handled
            }
            return .ignored
        }
    }
    
    private func navigateUp() {
        if currentChannelIndex > 0 {
            currentChannelIndex -= 1
        } else {
            currentChannelIndex = channelManager.channels.count - 1
        }
    }
    
    private func navigateDown() {
        if currentChannelIndex < channelManager.channels.count - 1 {
            currentChannelIndex += 1
        } else {
            currentChannelIndex = 0
        }
    }
    
    private func handleNumberInput(_ number: String) {
        typedNumber += number
        
        // Cancel existing timer
        clearNumberTask?.cancel()
        
        // Set timer to clear and jump
        clearNumberTask = Task {
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            
            if !Task.isCancelled {
                if let channelNumber = Int(typedNumber), channelNumber > 0 {
                    let index = channelNumber - 1
                    if channelManager.channels.indices.contains(index) {
                        selectChannel(at: index)
                    }
                }
                typedNumber = ""
            }
        }
    }
}

// MARK: - Channel Row

struct ChannelRow: View {
    let channel: Channel
    let number: Int
    let isSelected: Bool
    let isPlaying: Bool
    
    var body: some View {
        HStack(spacing: 12) {
            // Channel number
            Text("\(number)")
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.secondary)
                .frame(width: 30, alignment: .trailing)
            
            // Channel icon/thumbnail
            if let iconURL = channel.iconURL {
                AsyncImage(url: iconURL) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    Image(systemName: "tv")
                        .foregroundColor(.secondary)
                }
                .frame(width: 32, height: 32)
                .clipShape(RoundedRectangle(cornerRadius: 6))
            } else {
                Image(systemName: "tv")
                    .font(.title3)
                    .foregroundColor(.secondary)
                    .frame(width: 32, height: 32)
            }
            
            // Channel info
            VStack(alignment: .leading, spacing: 2) {
                Text(channel.name)
                    .font(.body)
                    .lineLimit(1)
                
                if let program = channel.currentProgram {
                    Text(program)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
            }
            
            Spacer()
            
            // Playing indicator
            if isPlaying {
                Image(systemName: "play.circle.fill")
                    .foregroundColor(.green)
            }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isSelected ? Color.accentColor.opacity(0.2) : Color.clear)
        )
        .contentShape(Rectangle())
    }
}

// MARK: - Keyboard Shortcut Hint

struct KeyboardShortcutHint: View {
    let key: String
    let description: String
    
    var body: some View {
        HStack(spacing: 4) {
            Text(key)
                .font(.caption2)
                .fontWeight(.medium)
                .padding(.horizontal, 4)
                .padding(.vertical, 2)
                .background(RoundedRectangle(cornerRadius: 3).fill(.secondary.opacity(0.2)))
            
            Text(description)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Channel Model Extension

extension Channel {
    var currentProgram: String? {
        // Placeholder - would come from EPG data
        return nil
    }
    
    var iconURL: URL? {
        // Placeholder - would come from channel configuration
        return nil
    }
}

// MARK: - Global Keyboard Shortcut Handler

class KeyboardShortcutHandler: ObservableObject {
    static let shared = KeyboardShortcutHandler()
    
    @Published var showChannelSwitcher = false
    
    private var eventMonitor: Any?
    
    func startMonitoring() {
        eventMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            return self?.handleKeyEvent(event)
        }
    }
    
    func stopMonitoring() {
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
            eventMonitor = nil
        }
    }
    
    private func handleKeyEvent(_ event: NSEvent) -> NSEvent? {
        // Command + G = Show channel guide/switcher
        if event.modifierFlags.contains(.command) && event.keyCode == 5 { // 'g'
            showChannelSwitcher.toggle()
            return nil
        }
        
        // Command + Up/Down = Channel up/down
        if event.modifierFlags.contains(.command) {
            if event.keyCode == 126 { // Up arrow
                NotificationCenter.default.post(name: .channelUp, object: nil)
                return nil
            } else if event.keyCode == 125 { // Down arrow
                NotificationCenter.default.post(name: .channelDown, object: nil)
                return nil
            }
        }
        
        return event
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let channelUp = Notification.Name("channelUp")
    static let channelDown = Notification.Name("channelDown")
    static let channelSelected = Notification.Name("channelSelected")
}

#Preview {
    ChannelSwitcher(
        isPresented: .constant(true),
        currentChannelIndex: .constant(0)
    )
    .environmentObject(ChannelManager())
}
