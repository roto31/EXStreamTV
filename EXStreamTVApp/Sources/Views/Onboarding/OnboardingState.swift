//
//  OnboardingState.swift
//  EXStreamTVApp
//
//  Manages the state of the onboarding wizard.
//

import Foundation
import SwiftUI

/// Steps in the onboarding wizard
enum OnboardingStep: Int, CaseIterable, Identifiable {
    case welcome = 0
    case aiSetup = 1
    case serverSetup = 2
    case mediaSources = 3
    case firstChannel = 4
    case complete = 5
    
    var id: Int { rawValue }
    
    var title: String {
        switch self {
        case .welcome: return "Welcome"
        case .aiSetup: return "AI Assistant"
        case .serverSetup: return "Server Setup"
        case .mediaSources: return "Media Sources"
        case .firstChannel: return "First Channel"
        case .complete: return "Complete"
        }
    }
    
    var icon: String {
        switch self {
        case .welcome: return "hand.wave"
        case .aiSetup: return "brain"
        case .serverSetup: return "server.rack"
        case .mediaSources: return "folder.badge.plus"
        case .firstChannel: return "tv"
        case .complete: return "checkmark.circle"
        }
    }
    
    var subtitle: String {
        switch self {
        case .welcome:
            return "Let's set up your personal TV streaming server"
        case .aiSetup:
            return "Configure AI to help create channels and troubleshoot"
        case .serverSetup:
            return "Configure the backend server settings"
        case .mediaSources:
            return "Connect your media libraries and folders"
        case .firstChannel:
            return "Create your first TV channel"
        case .complete:
            return "You're all set!"
        }
    }
}

/// Manages onboarding wizard state
@MainActor
class OnboardingState: ObservableObject {
    
    // MARK: - Singleton
    
    static let shared = OnboardingState()
    
    // MARK: - Published Properties
    
    @Published var currentStep: OnboardingStep = .welcome
    @Published var isOnboardingComplete: Bool = false
    @Published var showGroqSetup: Bool = false
    @Published var showLocalAISetup: Bool = false
    @Published var showOnboardingWindow: Bool = false
    
    // Step-specific state
    @Published var selectedAIOption: AISetupOption = .cloud
    @Published var serverPort: Int = 8411
    @Published var dataDirectory: String = ""
    @Published var serverStarted: Bool = false
    @Published var plexConnected: Bool = false
    @Published var jellyfinConnected: Bool = false
    @Published var embyConnected: Bool = false
    @Published var localFoldersAdded: Bool = false
    @Published var firstChannelCreated: Bool = false
    
    // MARK: - Computed Properties
    
    var canAdvance: Bool {
        switch currentStep {
        case .welcome:
            return true
        case .aiSetup:
            return true  // AI is optional
        case .serverSetup:
            return serverStarted
        case .mediaSources:
            return true  // Optional
        case .firstChannel:
            return true  // Optional
        case .complete:
            return false
        }
    }
    
    var isFirstStep: Bool {
        currentStep == .welcome
    }
    
    var isLastStep: Bool {
        currentStep == .complete
    }
    
    var progress: Double {
        Double(currentStep.rawValue) / Double(OnboardingStep.allCases.count - 1)
    }
    
    // MARK: - Initialization
    
    private init() {
        loadState()
    }
    
    // MARK: - Public Methods
    
    /// Check if onboarding should be shown
    func shouldShowOnboarding() -> Bool {
        return !isOnboardingComplete
    }
    
    /// Advance to the next step
    func advanceToNextStep() {
        guard let nextStep = OnboardingStep(rawValue: currentStep.rawValue + 1) else {
            completeOnboarding()
            return
        }
        
        withAnimation(.easeInOut) {
            currentStep = nextStep
        }
        
        saveState()
    }
    
    /// Go back to the previous step
    func goToPreviousStep() {
        guard let prevStep = OnboardingStep(rawValue: currentStep.rawValue - 1) else {
            return
        }
        
        withAnimation(.easeInOut) {
            currentStep = prevStep
        }
    }
    
    /// Skip to a specific step
    func skipToStep(_ step: OnboardingStep) {
        withAnimation(.easeInOut) {
            currentStep = step
        }
        saveState()
    }
    
    /// Complete the onboarding process
    func completeOnboarding() {
        isOnboardingComplete = true
        showOnboardingWindow = false
        saveState()
    }
    
    /// Reset onboarding state (for testing or re-running)
    func resetOnboarding() {
        currentStep = .welcome
        isOnboardingComplete = false
        selectedAIOption = .cloud
        serverStarted = false
        plexConnected = false
        jellyfinConnected = false
        embyConnected = false
        localFoldersAdded = false
        firstChannelCreated = false
        
        saveState()
    }
    
    // MARK: - Private Methods
    
    private func saveState() {
        let defaults = UserDefaults.standard
        defaults.set(currentStep.rawValue, forKey: "onboarding.currentStep")
        defaults.set(isOnboardingComplete, forKey: "onboarding.complete")
        defaults.set(selectedAIOption.rawValue, forKey: "onboarding.aiOption")
        defaults.set(serverPort, forKey: "onboarding.serverPort")
        defaults.set(dataDirectory, forKey: "onboarding.dataDirectory")
    }
    
    private func loadState() {
        let defaults = UserDefaults.standard
        
        if let stepRaw = defaults.object(forKey: "onboarding.currentStep") as? Int,
           let step = OnboardingStep(rawValue: stepRaw) {
            currentStep = step
        }
        
        isOnboardingComplete = defaults.bool(forKey: "onboarding.complete")
        
        if let aiOptionRaw = defaults.string(forKey: "onboarding.aiOption"),
           let aiOption = AISetupOption(rawValue: aiOptionRaw) {
            selectedAIOption = aiOption
        }
        
        if let port = defaults.object(forKey: "onboarding.serverPort") as? Int {
            serverPort = port
        }
        
        if let directory = defaults.string(forKey: "onboarding.dataDirectory") {
            dataDirectory = directory
        }
        
        // Set default data directory if not set
        if dataDirectory.isEmpty {
            dataDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)
                .first?
                .appendingPathComponent("EXStreamTV")
                .path ?? ""
        }
    }
}

/// AI setup options in onboarding
enum AISetupOption: String, CaseIterable, Identifiable {
    case cloud = "cloud"
    case local = "local"
    case hybrid = "hybrid"
    case skip = "skip"
    
    var id: String { rawValue }
    
    var title: String {
        switch self {
        case .cloud: return "Cloud AI (Recommended)"
        case .local: return "Local AI"
        case .hybrid: return "Hybrid"
        case .skip: return "Skip for Now"
        }
    }
    
    var subtitle: String {
        switch self {
        case .cloud: return "Free, instant setup via Groq"
        case .local: return "Runs on your Mac, works offline"
        case .hybrid: return "Cloud primary, local backup"
        case .skip: return "Configure AI later in Settings"
        }
    }
    
    var icon: String {
        switch self {
        case .cloud: return "cloud"
        case .local: return "desktopcomputer"
        case .hybrid: return "arrow.triangle.2.circlepath"
        case .skip: return "arrow.right.circle"
        }
    }
    
    var badge: String? {
        switch self {
        case .cloud: return "FREE"
        default: return nil
        }
    }
}
