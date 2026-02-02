//
//  LocalAISetupView.swift
//  EXStreamTVApp
//
//  Local AI setup view for onboarding - installs Ollama and downloads models.
//

import SwiftUI

struct LocalAISetupView: View {
    @EnvironmentObject var onboardingState: OnboardingState
    @EnvironmentObject var aiManager: AIProviderManager
    @Environment(\.dismiss) private var dismiss
    
    @State private var isCheckingOllama = false
    @State private var ollamaInstalled = false
    @State private var isDownloadingModel = false
    @State private var downloadProgress: Double = 0
    @State private var selectedModel: LocalModel?
    @State private var errorMessage: String?
    
    var body: some View {
        VStack(spacing: 24) {
            // Header
            VStack(spacing: 12) {
                Image(systemName: "desktopcomputer")
                    .font(.system(size: 64))
                    .foregroundStyle(.blue.gradient)
                
                Text("Set Up Local AI")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Run AI models directly on your Mac. Works completely offline.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            
            // Hardware info
            HStack {
                Image(systemName: "memorychip")
                    .foregroundColor(.blue)
                Text("Your Mac: \(aiManager.systemRAM)GB RAM")
                    .font(.headline)
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            
            // Recommended model
            VStack(alignment: .leading, spacing: 12) {
                Text("Recommended Model")
                    .font(.headline)
                
                ModelCard(
                    model: aiManager.recommendedLocalModel,
                    isSelected: selectedModel?.id == aiManager.recommendedLocalModel.id,
                    onSelect: {
                        selectedModel = aiManager.recommendedLocalModel
                    }
                )
            }
            .padding(.horizontal)
            
            // Other options
            if aiManager.systemRAM >= 8 {
                DisclosureGroup("Other Options") {
                    VStack(spacing: 8) {
                        ForEach(aiManager.compatibleModels.filter { $0.id != aiManager.recommendedLocalModel.id }, id: \.id) { model in
                            ModelCard(
                                model: model,
                                isSelected: selectedModel?.id == model.id,
                                onSelect: {
                                    selectedModel = model
                                }
                            )
                        }
                    }
                }
                .padding(.horizontal)
            }
            
            // Ollama status
            VStack(spacing: 12) {
                if isCheckingOllama {
                    HStack {
                        ProgressView()
                            .scaleEffect(0.8)
                        Text("Checking Ollama...")
                    }
                } else if ollamaInstalled {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text("Ollama is installed")
                    }
                } else {
                    VStack(spacing: 8) {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.orange)
                            Text("Ollama is not installed")
                        }
                        
                        Button {
                            installOllama()
                        } label: {
                            Label("Install Ollama", systemImage: "arrow.down.circle")
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            
            // Download progress
            if isDownloadingModel {
                VStack(spacing: 8) {
                    ProgressView(value: downloadProgress)
                        .progressViewStyle(.linear)
                    
                    Text("Downloading \(selectedModel?.name ?? "model")... \(Int(downloadProgress * 100))%")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal)
            }
            
            // Error message
            if let error = errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.horizontal)
            }
            
            Spacer()
            
            // Buttons
            VStack(spacing: 12) {
                Button {
                    downloadAndContinue()
                } label: {
                    if isDownloadingModel {
                        ProgressView()
                            .progressViewStyle(.circular)
                    } else {
                        HStack {
                            Image(systemName: "arrow.down.circle")
                            Text("Download Model (\(String(format: "%.1f", selectedModel?.sizeGB ?? aiManager.recommendedLocalModel.sizeGB))GB)")
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!ollamaInstalled || isDownloadingModel)
                
                Button("Skip - I'll set this up later") {
                    onboardingState.showLocalAISetup = false
                    onboardingState.advanceToNextStep()
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
            }
            .padding(.horizontal, 40)
        }
        .padding(.vertical, 32)
        .frame(width: 550)
        .task {
            selectedModel = aiManager.recommendedLocalModel
            await checkOllama()
        }
    }
    
    private func checkOllama() async {
        isCheckingOllama = true
        ollamaInstalled = await aiManager.checkOllamaStatus()
        isCheckingOllama = false
    }
    
    private func installOllama() {
        // Open Ollama website for download
        if let url = URL(string: "https://ollama.com/download") {
            NSWorkspace.shared.open(url)
        }
        
        // Also try brew install
        Task {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["brew", "install", "ollama"]
            
            do {
                try process.run()
                process.waitUntilExit()
                
                // Re-check after installation attempt
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await checkOllama()
            } catch {
                // Brew install failed, user should use the website
            }
        }
    }
    
    private func downloadAndContinue() {
        guard ollamaInstalled else { return }
        
        let model = selectedModel ?? aiManager.recommendedLocalModel
        isDownloadingModel = true
        downloadProgress = 0
        errorMessage = nil
        
        Task {
            do {
                try await aiManager.pullModel(model.id) { progress in
                    Task { @MainActor in
                        downloadProgress = progress
                    }
                }
                
                aiManager.localModel = model.id
                aiManager.providerType = onboardingState.selectedAIOption == .hybrid ? .hybrid : .local
                
                onboardingState.showLocalAISetup = false
                onboardingState.advanceToNextStep()
            } catch {
                errorMessage = "Download failed: \(error.localizedDescription)"
            }
            
            isDownloadingModel = false
        }
    }
}

// MARK: - Model Card

struct ModelCard: View {
    let model: LocalModel
    let isSelected: Bool
    let onSelect: () -> Void
    
    var body: some View {
        Button(action: onSelect) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(model.name)
                            .font(.headline)
                        
                        Text("\(String(format: "%.1f", model.sizeGB))GB")
                            .font(.caption)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.gray.opacity(0.2))
                            .clipShape(Capsule())
                    }
                    
                    Text(model.description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text(model.recommendedFor)
                        .font(.caption2)
                        .foregroundColor(.orange)
                }
                
                Spacer()
                
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isSelected ? .blue : .gray)
                    .font(.title2)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? Color.blue.opacity(0.1) : Color.gray.opacity(0.05))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    LocalAISetupView()
        .environmentObject(OnboardingState.shared)
        .environmentObject(AIProviderManager.shared)
}
