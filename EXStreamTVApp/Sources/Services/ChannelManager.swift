//
//  ChannelManager.swift
//  EXStreamTVApp
//
//  Manages channel information and provides quick access to channel controls.
//

import Foundation
import Combine

@MainActor
class ChannelManager: ObservableObject {
    // MARK: - Published Properties
    
    @Published var channels: [Channel] = []
    @Published var activeChannels: [Channel] = []
    @Published var isLoading = false
    @Published var lastError: String?
    
    // MARK: - Private Properties
    
    private var refreshTimer: Timer?
    private let refreshInterval: TimeInterval = 10.0
    
    // MARK: - Computed Properties
    
    var port: Int {
        UserDefaults.standard.integer(forKey: "serverPort")
    }
    
    var baseURL: URL? {
        URL(string: "http://localhost:\(port)")
    }
    
    // MARK: - Initialization
    
    init() {
        startAutoRefresh()
    }
    
    deinit {
        refreshTimer?.invalidate()
    }
    
    // MARK: - Public Methods
    
    func refresh() async {
        isLoading = true
        lastError = nil
        
        await fetchChannels()
        await fetchActiveChannels()
        
        isLoading = false
    }
    
    func startChannel(_ channelId: Int) async -> Bool {
        guard let url = baseURL?.appendingPathComponent("/api/channels/\(channelId)/start") else {
            return false
        }
        
        do {
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.timeoutInterval = 10
            
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 200 {
                    await refresh()
                    return true
                }
            }
        } catch {
            lastError = error.localizedDescription
        }
        
        return false
    }
    
    func stopChannel(_ channelId: Int) async -> Bool {
        guard let url = baseURL?.appendingPathComponent("/api/channels/\(channelId)/stop") else {
            return false
        }
        
        do {
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.timeoutInterval = 10
            
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 200 {
                    await refresh()
                    return true
                }
            }
        } catch {
            lastError = error.localizedDescription
        }
        
        return false
    }
    
    func openChannelStream(_ channelId: Int) {
        let port = self.port
        if let url = URL(string: "http://localhost:\(port)/channels/\(channelId)/stream.m3u8") {
            NSWorkspace.shared.open(url)
        }
    }
    
    // MARK: - Private Methods
    
    private func fetchChannels() async {
        guard let url = baseURL?.appendingPathComponent("/api/channels") else { return }
        
        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 5
            
            let (data, _) = try await URLSession.shared.data(for: request)
            channels = try JSONDecoder().decode([Channel].self, from: data)
        } catch {
            // Keep existing channels on error
        }
    }
    
    private func fetchActiveChannels() async {
        guard let url = baseURL?.appendingPathComponent("/api/dashboard/active-streams") else { return }
        
        do {
            var request = URLRequest(url: url)
            request.timeoutInterval = 5
            
            let (data, _) = try await URLSession.shared.data(for: request)
            let streams = try JSONDecoder().decode([ActiveStream].self, from: data)
            
            // Map to channels
            let activeIds = Set(streams.map { $0.channelId })
            activeChannels = channels.filter { activeIds.contains($0.id) }
        } catch {
            activeChannels = []
        }
    }
    
    private func startAutoRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: refreshInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.refresh()
            }
        }
    }
}

// MARK: - Supporting Types

struct Channel: Codable, Identifiable {
    let id: Int
    let number: Int
    let name: String
    let logoUrl: String?
    let group: String?
    let isEnabled: Bool
    
    enum CodingKeys: String, CodingKey {
        case id
        case number
        case name
        case logoUrl = "logo_url"
        case group
        case isEnabled = "is_enabled"
    }
    
    var displayName: String {
        "\(number). \(name)"
    }
}

struct ActiveStream: Codable {
    let channelId: Int
    let channelName: String
    let channelNumber: Int
    let currentItem: String?
    let viewers: Int
    let uptimeMinutes: Double
    
    enum CodingKeys: String, CodingKey {
        case channelId = "channel_id"
        case channelName = "channel_name"
        case channelNumber = "channel_number"
        case currentItem = "current_item"
        case viewers
        case uptimeMinutes = "uptime_minutes"
    }
}
