//
//  OnboardingWizard.swift
//  EXStreamTVApp
//
//  Main onboarding wizard view with 6 steps.
//

import SwiftUI

struct OnboardingWizard: View {
    @StateObject private var onboardingState = OnboardingState.shared
    @StateObject private var aiManager = AIProviderManager.shared
    @StateObject private var dependencyManager = DependencyManager.shared
    
    var body: some View {
        VStack(spacing: 0) {
            // Progress indicator
            OnboardingProgressBar(currentStep: onboardingState.currentStep)
            
            Divider()
            
            // Step content
            ZStack {
                ForEach(OnboardingStep.allCases, id: \.id) { step in
                    if step == onboardingState.currentStep {
                        stepView(for: step)
                            .transition(.asymmetric(
                                insertion: .move(edge: .trailing).combined(with: .opacity),
                                removal: .move(edge: .leading).combined(with: .opacity)
                            ))
                    }
                }
            }
            .animation(.easeInOut(duration: 0.3), value: onboardingState.currentStep)
            
            Divider()
            
            // Navigation buttons
            OnboardingNavigationBar()
        }
        .environmentObject(onboardingState)
        .environmentObject(aiManager)
        .environmentObject(dependencyManager)
        .sheet(isPresented: $onboardingState.showGroqSetup) {
            GroqSetupView()
                .environmentObject(onboardingState)
                .environmentObject(aiManager)
        }
        .sheet(isPresented: $onboardingState.showLocalAISetup) {
            LocalAISetupView()
                .environmentObject(onboardingState)
                .environmentObject(aiManager)
        }
        .frame(width: 700, height: 600)
    }
    
    @ViewBuilder
    private func stepView(for step: OnboardingStep) -> some View {
        switch step {
        case .welcome:
            WelcomeStep()
        case .aiSetup:
            AISetupStep()
        case .serverSetup:
            ServerSetupStep()
        case .mediaSources:
            MediaSourcesStep()
        case .firstChannel:
            FirstChannelStep()
        case .complete:
            CompleteStep()
        }
    }
}

// MARK: - Progress Bar

struct OnboardingProgressBar: View {
    let currentStep: OnboardingStep
    
    var body: some View {
        HStack(spacing: 0) {
            ForEach(OnboardingStep.allCases, id: \.id) { step in
                HStack(spacing: 8) {
                    // Step indicator
                    ZStack {
                        if step.rawValue < currentStep.rawValue {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                        } else if step == currentStep {
                            Image(systemName: step.icon)
                                .foregroundColor(.white)
                                .padding(6)
                                .background(Circle().fill(Color.blue))
                        } else {
                            Image(systemName: step.icon)
                                .foregroundColor(.gray)
                        }
                    }
                    .font(.body)
                    
                    // Step title (show only for current step on small screens)
                    if step == currentStep {
                        Text(step.title)
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                }
                
                if step != OnboardingStep.allCases.last {
                    // Connector line
                    Rectangle()
                        .fill(step.rawValue < currentStep.rawValue ? Color.green : Color.gray.opacity(0.3))
                        .frame(height: 2)
                }
            }
        }
        .padding()
    }
}

// MARK: - Navigation Bar

struct OnboardingNavigationBar: View {
    @EnvironmentObject var onboardingState: OnboardingState
    
    var body: some View {
        HStack {
            // Back button
            if !onboardingState.isFirstStep && !onboardingState.isLastStep {
                Button("Back") {
                    onboardingState.goToPreviousStep()
                }
                .buttonStyle(.bordered)
            }
            
            Spacer()
            
            // Skip button (for optional steps)
            if onboardingState.currentStep == .mediaSources || onboardingState.currentStep == .firstChannel {
                Button("Skip") {
                    onboardingState.advanceToNextStep()
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
            }
            
            // Next/Finish button
            if onboardingState.isLastStep {
                Button("Open Dashboard") {
                    onboardingState.completeOnboarding()
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            } else if onboardingState.canAdvance {
                Button("Next") {
                    onboardingState.advanceToNextStep()
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
    }
}

// MARK: - Step Views

struct WelcomeStep: View {
    @EnvironmentObject var onboardingState: OnboardingState
    @EnvironmentObject var dependencyManager: DependencyManager
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            // Logo/Icon
            Image(systemName: "tv.inset.filled")
                .font(.system(size: 80))
                .foregroundStyle(.blue.gradient)
            
            Text("Welcome to EXStreamTV")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            Text("Your personal TV streaming server")
                .font(.title3)
                .foregroundColor(.secondary)
            
            // Features
            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(icon: "tv", title: "Create Custom Channels", description: "Build TV channels from your media library")
                FeatureRow(icon: "brain", title: "AI-Powered", description: "Let AI help create and schedule your channels")
                FeatureRow(icon: "play.tv", title: "Stream Anywhere", description: "Watch on any device with HDHomeRun support")
            }
            .padding(24)
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            
            // Dependency status
            if dependencyManager.isCheckingAll {
                HStack {
                    ProgressView()
                        .scaleEffect(0.8)
                    Text("Checking dependencies...")
                }
                .foregroundColor(.secondary)
            } else if !dependencyManager.allRequiredInstalled {
                VStack(spacing: 8) {
                    Text("Missing Dependencies")
                        .font(.headline)
                        .foregroundColor(.orange)
                    
                    HStack(spacing: 16) {
                        DependencyStatusBadge(name: "Python", status: dependencyManager.pythonStatus)
                        DependencyStatusBadge(name: "FFmpeg", status: dependencyManager.ffmpegStatus)
                    }
                    
                    Button("Run Install Script") {
                        dependencyManager.runInstallScript()
                    }
                    .buttonStyle(.bordered)
                }
            } else {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("All dependencies installed")
                }
                .foregroundColor(.green)
            }
            
            Spacer()
        }
        .padding()
        .task {
            await dependencyManager.checkAllDependencies()
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)
                .frame(width: 32)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

struct DependencyStatusBadge: View {
    let name: String
    let status: DependencyStatus
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: status.isInstalled ? "checkmark.circle.fill" : "xmark.circle.fill")
            Text(name)
        }
        .font(.caption)
        .foregroundColor(status.isInstalled ? .green : .red)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            Capsule()
                .fill(status.isInstalled ? Color.green.opacity(0.1) : Color.red.opacity(0.1))
        )
    }
}

struct ServerSetupStep: View {
    @EnvironmentObject var onboardingState: OnboardingState
    @State private var isStarting = false
    
    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "server.rack")
                .font(.system(size: 48))
                .foregroundStyle(.green.gradient)
            
            Text("Server Setup")
                .font(.title)
                .fontWeight(.bold)
            
            Text("Configure and start the EXStreamTV backend server")
                .foregroundColor(.secondary)
            
            // Port configuration
            VStack(alignment: .leading, spacing: 8) {
                Text("Server Port")
                    .font(.headline)
                
                HStack {
                    TextField("Port", value: $onboardingState.serverPort, format: .number)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 100)
                    
                    Text("Default: 8411")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            
            // Data directory
            VStack(alignment: .leading, spacing: 8) {
                Text("Data Directory")
                    .font(.headline)
                
                HStack {
                    Text(onboardingState.dataDirectory)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    
                    Button("Change") {
                        selectDataDirectory()
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            
            // Start server button
            if onboardingState.serverStarted {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Server is running on port \(onboardingState.serverPort)")
                }
                .padding()
                .background(Color.green.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                Button {
                    startServer()
                } label: {
                    if isStarting {
                        ProgressView()
                            .progressViewStyle(.circular)
                    } else {
                        Label("Start Server", systemImage: "play.fill")
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
            
            Spacer()
        }
        .padding()
    }
    
    private func selectDataDirectory() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        
        if panel.runModal() == .OK, let url = panel.url {
            onboardingState.dataDirectory = url.path
        }
    }
    
    private func startServer() {
        isStarting = true
        
        // Simulate server start (actual implementation would use ServerManager)
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            onboardingState.serverStarted = true
            isStarting = false
        }
    }
}

struct MediaSourcesStep: View {
    @EnvironmentObject var onboardingState: OnboardingState
    
    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "folder.badge.plus")
                .font(.system(size: 48))
                .foregroundStyle(.purple.gradient)
            
            Text("Media Sources")
                .font(.title)
                .fontWeight(.bold)
            
            Text("Connect your media libraries (optional)")
                .foregroundColor(.secondary)
            
            // Plex
            MediaSourceCard(
                name: "Plex",
                icon: "play.square.stack",
                isConnected: onboardingState.plexConnected,
                onConnect: {
                    // TODO: Show Plex connection sheet
                }
            )
            
            // Jellyfin
            MediaSourceCard(
                name: "Jellyfin",
                icon: "server.rack",
                isConnected: onboardingState.jellyfinConnected,
                onConnect: {
                    // TODO: Show Jellyfin connection sheet
                }
            )
            
            // Local Folders
            MediaSourceCard(
                name: "Local Folders",
                icon: "folder",
                isConnected: onboardingState.localFoldersAdded,
                onConnect: {
                    selectLocalFolder()
                }
            )
            
            Spacer()
            
            Text("You can add more sources later in Settings")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
    }
    
    private func selectLocalFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        
        if panel.runModal() == .OK {
            onboardingState.localFoldersAdded = !panel.urls.isEmpty
        }
    }
}

struct MediaSourceCard: View {
    let name: String
    let icon: String
    let isConnected: Bool
    let onConnect: () -> Void
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)
                .frame(width: 44)
            
            Text(name)
                .font(.headline)
            
            Spacer()
            
            if isConnected {
                Label("Connected", systemImage: "checkmark.circle.fill")
                    .foregroundColor(.green)
            } else {
                Button("Connect") {
                    onConnect()
                }
                .buttonStyle(.bordered)
            }
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }
}

struct FirstChannelStep: View {
    @EnvironmentObject var onboardingState: OnboardingState
    @EnvironmentObject var aiManager: AIProviderManager
    
    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "tv")
                .font(.system(size: 48))
                .foregroundStyle(.orange.gradient)
            
            Text("Create Your First Channel")
                .font(.title)
                .fontWeight(.bold)
            
            Text("Choose how you'd like to create your first channel")
                .foregroundColor(.secondary)
            
            VStack(spacing: 12) {
                if aiManager.isConfigured {
                    ChannelCreationOption(
                        title: "AI-Assisted",
                        description: "Let AI help you create a channel based on your preferences",
                        icon: "brain",
                        action: {
                            // TODO: Show AI channel creation
                        }
                    )
                }
                
                ChannelCreationOption(
                    title: "Manual Configuration",
                    description: "Configure every aspect of your channel yourself",
                    icon: "slider.horizontal.3",
                    action: {
                        // TODO: Show manual channel creation
                    }
                )
                
                ChannelCreationOption(
                    title: "Import from M3U",
                    description: "Import an existing playlist file",
                    icon: "doc.badge.plus",
                    action: {
                        importM3U()
                    }
                )
            }
            .padding(.horizontal)
            
            Spacer()
        }
        .padding()
    }
    
    private func importM3U() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.init(filenameExtension: "m3u")!, .init(filenameExtension: "m3u8")!]
        
        if panel.runModal() == .OK, let _ = panel.url {
            onboardingState.firstChannelCreated = true
        }
    }
}

struct ChannelCreationOption: View {
    let title: String
    let description: String
    let icon: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(.blue)
                    .frame(width: 44)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(.primary)
                    Text(description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.gray)
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

struct CompleteStep: View {
    @EnvironmentObject var onboardingState: OnboardingState
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundStyle(.green.gradient)
            
            Text("You're All Set!")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            Text("EXStreamTV is ready to use")
                .font(.title3)
                .foregroundColor(.secondary)
            
            // Summary
            VStack(alignment: .leading, spacing: 12) {
                SummaryRow(label: "Server", value: "Running on port \(onboardingState.serverPort)")
                SummaryRow(label: "AI Assistant", value: aiStatusText)
                SummaryRow(label: "Media Sources", value: mediaSourcesText)
            }
            .padding(24)
            .background(Color.gray.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            
            Spacer()
            
            Text("Access the web dashboard at:")
                .foregroundColor(.secondary)
            
            Button("http://localhost:\(onboardingState.serverPort)") {
                if let url = URL(string: "http://localhost:\(onboardingState.serverPort)") {
                    NSWorkspace.shared.open(url)
                }
            }
            .font(.headline)
            .buttonStyle(.link)
            
            Spacer()
        }
        .padding()
    }
    
    private var aiStatusText: String {
        switch onboardingState.selectedAIOption {
        case .cloud: return "Cloud (Groq)"
        case .local: return "Local (Ollama)"
        case .hybrid: return "Hybrid"
        case .skip: return "Not configured"
        }
    }
    
    private var mediaSourcesText: String {
        var sources: [String] = []
        if onboardingState.plexConnected { sources.append("Plex") }
        if onboardingState.jellyfinConnected { sources.append("Jellyfin") }
        if onboardingState.embyConnected { sources.append("Emby") }
        if onboardingState.localFoldersAdded { sources.append("Local Folders") }
        
        return sources.isEmpty ? "None configured" : sources.joined(separator: ", ")
    }
}

struct SummaryRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
        }
    }
}

#Preview {
    OnboardingWizard()
}
