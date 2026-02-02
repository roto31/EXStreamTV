//
//  AIProviderManager.swift
//  EXStreamTVApp
//
//  Manages AI provider configuration for the Swift app.
//

import Foundation
import SwiftUI

/// Type of AI provider
enum AIProviderType: String, CaseIterable, Identifiable, Codable {
    case cloud = "cloud"
    case local = "local"
    case hybrid = "hybrid"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .cloud: return "Cloud AI"
        case .local: return "Local AI"
        case .hybrid: return "Hybrid"
        }
    }
    
    var description: String {
        switch self {
        case .cloud:
            return "Uses cloud services (Groq, SambaNova). Fast setup, requires internet."
        case .local:
            return "Runs on your Mac using Ollama. Works offline, requires more RAM."
        case .hybrid:
            return "Uses cloud when available, falls back to local when offline."
        }
    }
    
    var icon: String {
        switch self {
        case .cloud: return "cloud"
        case .local: return "desktopcomputer"
        case .hybrid: return "arrow.triangle.2.circlepath"
        }
    }
}

/// Cloud provider options
enum CloudProvider: String, CaseIterable, Identifiable, Codable {
    case groq = "groq"
    case sambanova = "sambanova"
    case openrouter = "openrouter"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .groq: return "Groq"
        case .sambanova: return "SambaNova"
        case .openrouter: return "OpenRouter"
        }
    }
    
    var description: String {
        switch self {
        case .groq:
            return "Free, ultra-fast inference. Recommended."
        case .sambanova:
            return "Free backup, 1M tokens/day."
        case .openrouter:
            return "$5 free credit, access to 100+ models."
        }
    }
    
    var signupURL: URL {
        switch self {
        case .groq:
            return URL(string: "https://console.groq.com/keys")!
        case .sambanova:
            return URL(string: "https://cloud.sambanova.ai")!
        case .openrouter:
            return URL(string: "https://openrouter.ai/keys")!
        }
    }
    
    var limits: String {
        switch self {
        case .groq:
            return "30 req/min, 14,400 req/day"
        case .sambanova:
            return "1M tokens/day, 120 req/min"
        case .openrouter:
            return "$5 free credit"
        }
    }
    
    var isFree: Bool {
        return true  // All currently free tier
    }
}

/// Local model information
struct LocalModel: Identifiable, Codable {
    let id: String
    let name: String
    let sizeGB: Double
    let ramRequiredGB: Int
    let tier: Int
    let description: String
    let recommendedFor: String
    let capabilities: [String]
    
    var isInstalled: Bool = false
    var canRun: Bool = true
    
    static let allModels: [LocalModel] = [
        LocalModel(
            id: "phi4-mini:3.8b-q4",
            name: "Phi-4 Mini (3.8B)",
            sizeGB: 2.5,
            ramRequiredGB: 4,
            tier: 1,
            description: "Best lightweight model - native function calling",
            recommendedFor: "4GB RAM, excellent structured output",
            capabilities: ["function_calling", "json_output", "reasoning"]
        ),
        LocalModel(
            id: "granite3.1:2b-instruct",
            name: "Granite 3.1 (2B)",
            sizeGB: 2.0,
            ramRequiredGB: 6,
            tier: 2,
            description: "IBM model with hallucination detection",
            recommendedFor: "8GB RAM, reliable tool calling",
            capabilities: ["function_calling", "hallucination_detection"]
        ),
        LocalModel(
            id: "qwen2.5:7b",
            name: "Qwen 2.5 (7B)",
            sizeGB: 4.4,
            ramRequiredGB: 8,
            tier: 2,
            description: "Best JSON output reliability",
            recommendedFor: "8GB+ RAM, excellent structured output",
            capabilities: ["json_output", "function_calling", "reasoning"]
        ),
        LocalModel(
            id: "qwen2.5:14b",
            name: "Qwen 2.5 (14B)",
            sizeGB: 9.0,
            ramRequiredGB: 16,
            tier: 3,
            description: "Recommended for full persona support",
            recommendedFor: "16GB RAM, all 6 personas work perfectly",
            capabilities: ["json_output", "function_calling", "reasoning", "personas"]
        ),
    ]
}

/// Manages AI provider configuration
@MainActor
class AIProviderManager: ObservableObject {
    
    // MARK: - Singleton
    
    static let shared = AIProviderManager()
    
    // MARK: - Published Properties
    
    @Published var providerType: AIProviderType = .cloud {
        didSet { saveConfiguration() }
    }
    
    @Published var cloudProvider: CloudProvider = .groq {
        didSet { saveConfiguration() }
    }
    
    @Published var cloudAPIKey: String = "" {
        didSet { saveConfiguration() }
    }
    
    @Published var cloudModel: String = "llama-3.3-70b-versatile" {
        didSet { saveConfiguration() }
    }
    
    @Published var localModel: String = "auto" {
        didSet { saveConfiguration() }
    }
    
    @Published var isConfigured: Bool = false
    @Published var isValidating: Bool = false
    @Published var validationError: String?
    @Published var installedLocalModels: [String] = []
    
    // MARK: - Computed Properties
    
    /// System RAM in GB
    var systemRAM: Int {
        var size: UInt64 = 0
        var len = MemoryLayout<UInt64>.size
        sysctlbyname("hw.memsize", &size, &len, nil, 0)
        return Int(size / (1024 * 1024 * 1024))
    }
    
    /// Recommended local model based on system RAM
    var recommendedLocalModel: LocalModel {
        let ram = systemRAM
        
        if ram < 6 {
            return LocalModel.allModels.first { $0.id == "phi4-mini:3.8b-q4" }!
        } else if ram < 12 {
            return LocalModel.allModels.first { $0.id == "granite3.1:2b-instruct" }!
        } else if ram < 24 {
            return LocalModel.allModels.first { $0.id == "qwen2.5:7b" }!
        } else {
            return LocalModel.allModels.first { $0.id == "qwen2.5:14b" }!
        }
    }
    
    /// Compatible local models based on system RAM
    var compatibleModels: [LocalModel] {
        let ram = systemRAM
        return LocalModel.allModels.filter { $0.ramRequiredGB <= ram }
    }
    
    /// Check if the current configuration is valid
    var isValid: Bool {
        switch providerType {
        case .cloud:
            return !cloudAPIKey.isEmpty
        case .local:
            return !localModel.isEmpty
        case .hybrid:
            return !cloudAPIKey.isEmpty || !localModel.isEmpty
        }
    }
    
    // MARK: - Initialization
    
    private init() {
        loadConfiguration()
    }
    
    // MARK: - Public Methods
    
    /// Validate the Groq API key
    func validateGroqKey(_ key: String) async -> Bool {
        isValidating = true
        validationError = nil
        
        defer { isValidating = false }
        
        guard let url = URL(string: "https://api.groq.com/openai/v1/models") else {
            validationError = "Invalid URL"
            return false
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 10
        
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 200 {
                    isConfigured = true
                    return true
                } else if httpResponse.statusCode == 401 {
                    validationError = "Invalid API key"
                } else {
                    validationError = "Server error: \(httpResponse.statusCode)"
                }
            }
        } catch {
            validationError = error.localizedDescription
        }
        
        return false
    }
    
    /// Check if Ollama is installed and running
    func checkOllamaStatus() async -> Bool {
        guard let url = URL(string: "http://localhost:11434/api/tags") else {
            return false
        }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                // Parse installed models
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let models = json["models"] as? [[String: Any]] {
                    installedLocalModels = models.compactMap { $0["name"] as? String }
                }
                return true
            }
        } catch {
            // Ollama not running or not installed
        }
        
        return false
    }
    
    /// Pull (download) an Ollama model
    func pullModel(_ modelId: String, progress: @escaping (Double) -> Void) async throws {
        guard let url = URL(string: "http://localhost:11434/api/pull") else {
            throw NSError(domain: "AIProviderManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"])
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["name": modelId]
        request.httpBody = try JSONEncoder().encode(body)
        
        // Use streaming response to track progress
        let (bytes, _) = try await URLSession.shared.bytes(for: request)
        
        for try await line in bytes.lines {
            if let data = line.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                
                if let completed = json["completed"] as? Int64,
                   let total = json["total"] as? Int64,
                   total > 0 {
                    let progressValue = Double(completed) / Double(total)
                    progress(progressValue)
                }
                
                if json["status"] as? String == "success" {
                    progress(1.0)
                    installedLocalModels.append(modelId)
                    return
                }
            }
        }
    }
    
    /// Send configuration to the backend API
    func syncToBackend() async throws {
        // Build API request to update backend configuration
        guard let baseURL = UserDefaults.standard.string(forKey: "serverURL") ?? Optional("http://localhost:8411"),
              let url = URL(string: "\(baseURL)/api/ai/configure") else {
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let config: [String: Any] = [
            "provider_type": providerType.rawValue,
            "cloud_provider": cloudProvider.rawValue,
            "cloud_api_key": cloudAPIKey,
            "cloud_model": cloudModel,
            "local_model": localModel,
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: config)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        
        if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode != 200 {
            throw NSError(domain: "AIProviderManager", code: httpResponse.statusCode)
        }
    }
    
    // MARK: - Private Methods
    
    private func saveConfiguration() {
        let defaults = UserDefaults.standard
        defaults.set(providerType.rawValue, forKey: "ai.providerType")
        defaults.set(cloudProvider.rawValue, forKey: "ai.cloudProvider")
        defaults.set(cloudModel, forKey: "ai.cloudModel")
        defaults.set(localModel, forKey: "ai.localModel")
        
        // Store API key in Keychain for security
        if !cloudAPIKey.isEmpty {
            saveAPIKeyToKeychain(cloudAPIKey)
        }
    }
    
    private func loadConfiguration() {
        let defaults = UserDefaults.standard
        
        if let typeRaw = defaults.string(forKey: "ai.providerType"),
           let type = AIProviderType(rawValue: typeRaw) {
            providerType = type
        }
        
        if let providerRaw = defaults.string(forKey: "ai.cloudProvider"),
           let provider = CloudProvider(rawValue: providerRaw) {
            cloudProvider = provider
        }
        
        if let model = defaults.string(forKey: "ai.cloudModel") {
            cloudModel = model
        }
        
        if let model = defaults.string(forKey: "ai.localModel") {
            localModel = model
        }
        
        // Load API key from Keychain
        cloudAPIKey = loadAPIKeyFromKeychain() ?? ""
        
        isConfigured = isValid
    }
    
    private func saveAPIKeyToKeychain(_ key: String) {
        let data = key.data(using: .utf8)!
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.exstreamtv.aikey",
            kSecAttrAccount as String: cloudProvider.rawValue,
        ]
        
        SecItemDelete(query as CFDictionary)
        
        var addQuery = query
        addQuery[kSecValueData as String] = data
        
        SecItemAdd(addQuery as CFDictionary, nil)
    }
    
    private func loadAPIKeyFromKeychain() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.exstreamtv.aikey",
            kSecAttrAccount as String: cloudProvider.rawValue,
            kSecReturnData as String: true,
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        if status == errSecSuccess, let data = result as? Data {
            return String(data: data, encoding: .utf8)
        }
        
        return nil
    }
}
