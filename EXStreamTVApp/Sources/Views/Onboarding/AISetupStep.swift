//
//  AISetupStep.swift
//  EXStreamTVApp
//
//  AI setup step in the onboarding wizard.
//

import SwiftUI

struct AISetupStep: View {
    @EnvironmentObject var onboardingState: OnboardingState
    @EnvironmentObject var aiManager: AIProviderManager
    
    var body: some View {
        VStack(spacing: 24) {
            // Header
            VStack(spacing: 8) {
                Image(systemName: "brain")
                    .font(.system(size: 48))
                    .foregroundStyle(.purple.gradient)
                
                Text("AI Assistant Setup")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("EXStreamTV uses AI to help create channels and troubleshoot issues")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.bottom, 16)
            
            // Options
            VStack(spacing: 12) {
                ForEach(AISetupOption.allCases) { option in
                    AIOptionCard(
                        option: option,
                        isSelected: onboardingState.selectedAIOption == option,
                        ramInfo: option == .local ? "Your Mac: \(aiManager.systemRAM)GB RAM" : nil,
                        recommendedModel: option == .local ? aiManager.recommendedLocalModel.name : nil
                    ) {
                        withAnimation(.spring(response: 0.3)) {
                            onboardingState.selectedAIOption = option
                        }
                    }
                }
            }
            .padding(.horizontal)
            
            Spacer()
            
            // Continue button
            Button {
                handleContinue()
            } label: {
                Text("Continue")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .padding(.horizontal, 40)
        }
        .padding(.vertical, 32)
    }
    
    private func handleContinue() {
        switch onboardingState.selectedAIOption {
        case .cloud, .hybrid:
            onboardingState.showGroqSetup = true
        case .local:
            onboardingState.showLocalAISetup = true
        case .skip:
            onboardingState.advanceToNextStep()
        }
    }
}

// MARK: - AI Option Card

struct AIOptionCard: View {
    let option: AISetupOption
    let isSelected: Bool
    var ramInfo: String?
    var recommendedModel: String?
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                // Icon
                Image(systemName: option.icon)
                    .font(.title2)
                    .foregroundColor(isSelected ? .white : .blue)
                    .frame(width: 44, height: 44)
                    .background(isSelected ? Color.blue : Color.blue.opacity(0.1))
                    .clipShape(Circle())
                
                // Text content
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(option.title)
                            .font(.headline)
                            .foregroundColor(.primary)
                        
                        if let badge = option.badge {
                            Text(badge)
                                .font(.caption2)
                                .fontWeight(.bold)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.green)
                                .foregroundColor(.white)
                                .clipShape(Capsule())
                        }
                    }
                    
                    Text(option.subtitle)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    if let ramInfo = ramInfo {
                        Text(ramInfo)
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                    
                    if let model = recommendedModel {
                        Text("Recommended: \(model)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                // Selection indicator
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundColor(isSelected ? .blue : .gray.opacity(0.3))
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
    AISetupStep()
        .environmentObject(OnboardingState.shared)
        .environmentObject(AIProviderManager.shared)
        .frame(width: 600, height: 600)
}
