//
//  AISettingsView.swift
//  EXStreamTVApp
//
//  Settings view for configuring AI providers.
//

import SwiftUI

struct AISettingsView: View {
    @EnvironmentObject var aiManager: AIProviderManager
    @State private var isValidating = false
    @State private var showAPIKeyInput = false
    @State private var tempAPIKey = ""
    @State private var validationResult: Bool?
    @State private var isCheckingOllama = false
    @State private var ollamaAvailable = false
    
    var body: some View {
        Form {
            // Provider Type Selection
            Section {
                Picker("Provider Type", selection: $aiManager.providerType) {
                    ForEach(AIProviderType.allCases) { type in
                        Label(type.displayName, systemImage: type.icon)
                            .tag(type)
                    }
                }
                .pickerStyle(.segmented)
                
                Text(aiManager.providerType.description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            } header: {
                Text("AI Provider")
            }
            
            // Cloud Configuration
            if aiManager.providerType == .cloud || aiManager.providerType == .hybrid {
                Section {
                    Picker("Cloud Service", selection: $aiManager.cloudProvider) {
                        ForEach(CloudProvider.allCases) { provider in
                            VStack(alignment: .leading) {
                                Text(provider.displayName)
                                Text(provider.limits)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .tag(provider)
                        }
                    }
                    
                    HStack {
                        if aiManager.cloudAPIKey.isEmpty {
                            Text("API Key: Not configured")
                                .foregroundColor(.orange)
                        } else {
                            Text("API Key: ••••••••\(String(aiManager.cloudAPIKey.suffix(4)))")
                                .foregroundColor(.green)
                        }
                        
                        Spacer()
                        
                        Button(aiManager.cloudAPIKey.isEmpty ? "Add Key" : "Change") {
                            tempAPIKey = ""
                            showAPIKeyInput = true
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    Button {
                        NSWorkspace.shared.open(aiManager.cloudProvider.signupURL)
                    } label: {
                        Label("Get Free API Key", systemImage: "arrow.up.right.square")
                    }
                    .buttonStyle(.link)
                } header: {
                    Text("Cloud Provider")
                } footer: {
                    Text(aiManager.cloudProvider.description)
                }
            }
            
            // Local Configuration
            if aiManager.providerType == .local || aiManager.providerType == .hybrid {
                Section {
                    HStack {
                        Image(systemName: "memorychip")
                            .foregroundColor(.blue)
                        Text("Your Mac: \(aiManager.systemRAM)GB RAM")
                    }
                    .padding(.vertical, 4)
                    
                    HStack {
                        Image(systemName: ollamaAvailable ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundColor(ollamaAvailable ? .green : .red)
                        Text(ollamaAvailable ? "Ollama is running" : "Ollama not available")
                        
                        Spacer()
                        
                        if isCheckingOllama {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Button("Check") {
                                Task { await checkOllama() }
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                    
                    if ollamaAvailable {
                        Picker("Model", selection: $aiManager.localModel) {
                            Text("Auto-select").tag("auto")
                            
                            ForEach(aiManager.compatibleModels, id: \.id) { model in
                                HStack {
                                    Text(model.name)
                                    if aiManager.installedLocalModels.contains(where: { $0.contains(model.id.split(separator: ":").first ?? "") }) {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundColor(.green)
                                            .font(.caption)
                                    }
                                }
                                .tag(model.id)
                            }
                        }
                        
                        if !aiManager.installedLocalModels.isEmpty {
                            DisclosureGroup("Installed Models (\(aiManager.installedLocalModels.count))") {
                                ForEach(aiManager.installedLocalModels, id: \.self) { model in
                                    Text(model)
                                        .font(.caption)
                                }
                            }
                        }
                    }
                } header: {
                    Text("Local AI (Ollama)")
                } footer: {
                    if !ollamaAvailable {
                        Text("Install Ollama to use local AI models.")
                    } else {
                        Text("Recommended: \(aiManager.recommendedLocalModel.name)")
                    }
                }
            }
            
            // Status
            Section {
                HStack {
                    Image(systemName: aiManager.isConfigured ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundColor(aiManager.isConfigured ? .green : .orange)
                    
                    Text(aiManager.isConfigured ? "AI is configured and ready" : "AI configuration incomplete")
                    
                    Spacer()
                    
                    if aiManager.isConfigured {
                        Button("Test") {
                            // TODO: Add test generation
                        }
                        .buttonStyle(.bordered)
                    }
                }
            } header: {
                Text("Status")
            }
        }
        .formStyle(.grouped)
        .sheet(isPresented: $showAPIKeyInput) {
            APIKeyInputSheet(
                provider: aiManager.cloudProvider,
                apiKey: $tempAPIKey,
                isValidating: $isValidating,
                validationResult: $validationResult,
                onSave: {
                    Task {
                        let isValid = await aiManager.validateGroqKey(tempAPIKey)
                        validationResult = isValid
                        if isValid {
                            aiManager.cloudAPIKey = tempAPIKey
                            showAPIKeyInput = false
                        }
                    }
                },
                onCancel: {
                    showAPIKeyInput = false
                }
            )
        }
        .task {
            await checkOllama()
        }
    }
    
    private func checkOllama() async {
        isCheckingOllama = true
        ollamaAvailable = await aiManager.checkOllamaStatus()
        isCheckingOllama = false
    }
}

// MARK: - API Key Input Sheet

struct APIKeyInputSheet: View {
    let provider: CloudProvider
    @Binding var apiKey: String
    @Binding var isValidating: Bool
    @Binding var validationResult: Bool?
    let onSave: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "key.fill")
                .font(.system(size: 48))
                .foregroundStyle(.blue)
            
            Text("Enter \(provider.displayName) API Key")
                .font(.title2)
                .fontWeight(.semibold)
            
            Text("Your API key is stored securely in the macOS Keychain.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            SecureField("Paste your API key here", text: $apiKey)
                .textFieldStyle(.roundedBorder)
                .frame(width: 400)
            
            if let result = validationResult {
                HStack {
                    Image(systemName: result ? "checkmark.circle.fill" : "xmark.circle.fill")
                    Text(result ? "Valid API key!" : "Invalid API key")
                }
                .foregroundColor(result ? .green : .red)
            }
            
            HStack(spacing: 16) {
                Button("Cancel", action: onCancel)
                    .buttonStyle(.bordered)
                
                Button {
                    onSave()
                } label: {
                    if isValidating {
                        ProgressView()
                            .scaleEffect(0.7)
                    } else {
                        Text("Validate & Save")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(apiKey.isEmpty || isValidating)
            }
            
            Button {
                NSWorkspace.shared.open(provider.signupURL)
            } label: {
                Label("Get Free API Key from \(provider.displayName)", systemImage: "arrow.up.right.square")
            }
            .buttonStyle(.link)
        }
        .padding(40)
        .frame(width: 500)
    }
}

#Preview {
    AISettingsView()
        .environmentObject(AIProviderManager.shared)
        .frame(width: 600, height: 700)
}
