//
//  GroqSetupView.swift
//  EXStreamTVApp
//
//  Groq API key setup wizard for onboarding.
//

import SwiftUI

struct GroqSetupView: View {
    @EnvironmentObject var onboardingState: OnboardingState
    @EnvironmentObject var aiManager: AIProviderManager
    @Environment(\.dismiss) private var dismiss
    
    @State private var apiKey: String = ""
    @State private var isValidating = false
    @State private var validationResult: ValidationResult?
    
    var body: some View {
        VStack(spacing: 24) {
            // Header with Groq branding
            VStack(spacing: 12) {
                Image(systemName: "bolt.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(.orange.gradient)
                
                Text("Set Up Groq Cloud")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Groq provides free, ultra-fast AI inference. Get your API key in 30 seconds.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            
            // Step-by-step instructions
            VStack(alignment: .leading, spacing: 12) {
                InstructionRow(number: 1, text: "Go to console.groq.com")
                InstructionRow(number: 2, text: "Sign in with Google or GitHub")
                InstructionRow(number: 3, text: "Copy your API key")
                InstructionRow(number: 4, text: "Paste it below")
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            
            // Open browser button
            Button {
                NSWorkspace.shared.open(URL(string: "https://console.groq.com/keys")!)
            } label: {
                Label("Open Groq Console", systemImage: "arrow.up.right.square")
            }
            .buttonStyle(.bordered)
            
            // API Key input
            VStack(alignment: .leading, spacing: 8) {
                Text("API Key")
                    .font(.headline)
                
                HStack {
                    SecureField("Paste your Groq API key here", text: $apiKey)
                        .textFieldStyle(.roundedBorder)
                    
                    if isValidating {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else if let result = validationResult {
                        Image(systemName: result.isValid ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundColor(result.isValid ? .green : .red)
                            .font(.title2)
                    }
                }
                
                if let result = validationResult, !result.isValid, let message = result.errorMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
            .padding(.horizontal)
            
            Spacer()
            
            // Buttons
            VStack(spacing: 12) {
                Button {
                    validateAndContinue()
                } label: {
                    if isValidating {
                        ProgressView()
                            .progressViewStyle(.circular)
                    } else {
                        Text("Validate & Continue")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(apiKey.isEmpty || isValidating)
                
                Button("Skip - I'll set this up later") {
                    onboardingState.showGroqSetup = false
                    onboardingState.advanceToNextStep()
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
            }
            .padding(.horizontal, 40)
        }
        .padding(.vertical, 32)
        .frame(width: 500)
    }
    
    private func validateAndContinue() {
        isValidating = true
        validationResult = nil
        
        Task {
            let isValid = await aiManager.validateGroqKey(apiKey)
            
            if isValid {
                validationResult = ValidationResult(isValid: true)
                aiManager.cloudAPIKey = apiKey
                aiManager.providerType = onboardingState.selectedAIOption == .hybrid ? .hybrid : .cloud
                
                // Brief delay to show success
                try? await Task.sleep(nanoseconds: 500_000_000)
                
                onboardingState.showGroqSetup = false
                onboardingState.advanceToNextStep()
            } else {
                validationResult = ValidationResult(
                    isValid: false,
                    errorMessage: aiManager.validationError ?? "Invalid API key"
                )
            }
            
            isValidating = false
        }
    }
}

// MARK: - Supporting Views

struct InstructionRow: View {
    let number: Int
    let text: String
    
    var body: some View {
        HStack(spacing: 12) {
            Text("\(number)")
                .font(.headline)
                .foregroundColor(.white)
                .frame(width: 28, height: 28)
                .background(Circle().fill(Color.blue))
            
            Text(text)
                .font(.body)
        }
    }
}

struct ValidationResult {
    let isValid: Bool
    var errorMessage: String? = nil
}

#Preview {
    GroqSetupView()
        .environmentObject(OnboardingState.shared)
        .environmentObject(AIProviderManager.shared)
}
