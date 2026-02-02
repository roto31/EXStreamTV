//
//  PlayerView.swift
//  EXStreamTVApp
//
//  Native video player for in-app channel playback.
//

import AVKit
import SwiftUI

struct PlayerView: View {
    let channelURL: URL
    let channelName: String
    
    @StateObject private var playerController = PlayerController()
    @State private var showControls = true
    @State private var hideControlsTask: Task<Void, Never>?
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        ZStack {
            // Video player
            VideoPlayerView(player: playerController.player)
                .ignoresSafeArea()
                .onTapGesture {
                    toggleControls()
                }
            
            // Overlay controls
            if showControls {
                VStack {
                    // Top bar
                    HStack {
                        Button {
                            dismiss()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.title)
                                .foregroundColor(.white)
                        }
                        .buttonStyle(.plain)
                        
                        Spacer()
                        
                        Text(channelName)
                            .font(.headline)
                            .foregroundColor(.white)
                        
                        Spacer()
                        
                        // Picture in Picture button
                        if playerController.isPiPSupported {
                            Button {
                                playerController.togglePiP()
                            } label: {
                                Image(systemName: playerController.isPiPActive ? "pip.exit" : "pip.enter")
                                    .font(.title2)
                                    .foregroundColor(.white)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding()
                    .background(
                        LinearGradient(
                            colors: [.black.opacity(0.7), .clear],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    
                    Spacer()
                    
                    // Bottom controls
                    HStack(spacing: 20) {
                        // Play/Pause
                        Button {
                            playerController.togglePlayback()
                        } label: {
                            Image(systemName: playerController.isPlaying ? "pause.fill" : "play.fill")
                                .font(.title)
                                .foregroundColor(.white)
                        }
                        .buttonStyle(.plain)
                        
                        // Volume
                        HStack(spacing: 8) {
                            Image(systemName: playerController.isMuted ? "speaker.slash.fill" : "speaker.wave.2.fill")
                                .foregroundColor(.white)
                                .onTapGesture {
                                    playerController.toggleMute()
                                }
                            
                            Slider(value: $playerController.volume, in: 0...1)
                                .frame(width: 100)
                                .tint(.white)
                        }
                        
                        Spacer()
                        
                        // Quality indicator
                        if let quality = playerController.currentQuality {
                            Text(quality)
                                .font(.caption)
                                .foregroundColor(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Capsule().fill(.white.opacity(0.3)))
                        }
                        
                        // Fullscreen
                        Button {
                            playerController.toggleFullscreen()
                        } label: {
                            Image(systemName: playerController.isFullscreen ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right")
                                .font(.title2)
                                .foregroundColor(.white)
                        }
                        .buttonStyle(.plain)
                    }
                    .padding()
                    .background(
                        LinearGradient(
                            colors: [.clear, .black.opacity(0.7)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                }
                .transition(.opacity)
            }
            
            // Loading indicator
            if playerController.isLoading {
                ProgressView()
                    .scaleEffect(1.5)
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
            }
            
            // Error overlay
            if let error = playerController.error {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.orange)
                    
                    Text("Playback Error")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                        .multilineTextAlignment(.center)
                    
                    Button("Retry") {
                        playerController.play(url: channelURL)
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding(32)
                .background(RoundedRectangle(cornerRadius: 16).fill(.black.opacity(0.8)))
            }
        }
        .background(Color.black)
        .onAppear {
            playerController.play(url: channelURL)
            scheduleHideControls()
        }
        .onDisappear {
            playerController.stop()
        }
        .onHover { hovering in
            if hovering {
                showControls = true
                scheduleHideControls()
            }
        }
    }
    
    private func toggleControls() {
        withAnimation(.easeInOut(duration: 0.2)) {
            showControls.toggle()
        }
        
        if showControls {
            scheduleHideControls()
        }
    }
    
    private func scheduleHideControls() {
        hideControlsTask?.cancel()
        hideControlsTask = Task {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            if !Task.isCancelled && playerController.isPlaying {
                withAnimation(.easeInOut(duration: 0.2)) {
                    showControls = false
                }
            }
        }
    }
}

// MARK: - Video Player View

struct VideoPlayerView: NSViewRepresentable {
    let player: AVPlayer
    
    func makeNSView(context: Context) -> AVPlayerView {
        let view = AVPlayerView()
        view.player = player
        view.controlsStyle = .none
        view.showsFullScreenToggleButton = false
        view.allowsPictureInPicturePlayback = true
        return view
    }
    
    func updateNSView(_ nsView: AVPlayerView, context: Context) {
        nsView.player = player
    }
}

// MARK: - Player Controller

@MainActor
class PlayerController: ObservableObject {
    @Published var player = AVPlayer()
    @Published var isPlaying = false
    @Published var isLoading = false
    @Published var isMuted = false
    @Published var volume: Float = 1.0 {
        didSet { player.volume = volume }
    }
    @Published var isPiPActive = false
    @Published var isFullscreen = false
    @Published var currentQuality: String?
    @Published var error: String?
    
    private var playerItemObserver: NSKeyValueObservation?
    private var timeControlObserver: NSKeyValueObservation?
    
    var isPiPSupported: Bool {
        return AVPictureInPictureController.isPictureInPictureSupported()
    }
    
    init() {
        setupObservers()
    }
    
    func play(url: URL) {
        error = nil
        isLoading = true
        
        let playerItem = AVPlayerItem(url: url)
        player.replaceCurrentItem(with: playerItem)
        
        // Observe player item status
        playerItemObserver = playerItem.observe(\.status) { [weak self] item, _ in
            Task { @MainActor in
                switch item.status {
                case .readyToPlay:
                    self?.isLoading = false
                    self?.player.play()
                    self?.isPlaying = true
                    self?.updateQualityInfo()
                case .failed:
                    self?.isLoading = false
                    self?.error = item.error?.localizedDescription ?? "Unknown error"
                default:
                    break
                }
            }
        }
    }
    
    func stop() {
        player.pause()
        player.replaceCurrentItem(with: nil)
        isPlaying = false
    }
    
    func togglePlayback() {
        if isPlaying {
            player.pause()
        } else {
            player.play()
        }
        isPlaying.toggle()
    }
    
    func toggleMute() {
        isMuted.toggle()
        player.isMuted = isMuted
    }
    
    func togglePiP() {
        // PiP requires additional setup with AVPictureInPictureController
        isPiPActive.toggle()
    }
    
    func toggleFullscreen() {
        isFullscreen.toggle()
        
        if let window = NSApplication.shared.keyWindow {
            if isFullscreen {
                window.toggleFullScreen(nil)
            } else {
                window.toggleFullScreen(nil)
            }
        }
    }
    
    private func setupObservers() {
        timeControlObserver = player.observe(\.timeControlStatus) { [weak self] player, _ in
            Task { @MainActor in
                self?.isPlaying = player.timeControlStatus == .playing
                self?.isLoading = player.timeControlStatus == .waitingToPlayAtSpecifiedRate
            }
        }
    }
    
    private func updateQualityInfo() {
        guard let currentItem = player.currentItem else { return }
        
        // Try to get video track info
        if let videoTrack = currentItem.asset.tracks(withMediaType: .video).first {
            let size = videoTrack.naturalSize
            let height = Int(abs(size.height))
            
            if height >= 2160 {
                currentQuality = "4K"
            } else if height >= 1080 {
                currentQuality = "1080p"
            } else if height >= 720 {
                currentQuality = "720p"
            } else if height >= 480 {
                currentQuality = "480p"
            } else {
                currentQuality = "\(height)p"
            }
        }
    }
}

// MARK: - Player Window

struct PlayerWindow: View {
    let channelURL: URL
    let channelName: String
    
    var body: some View {
        PlayerView(channelURL: channelURL, channelName: channelName)
            .frame(minWidth: 640, minHeight: 360)
            .frame(idealWidth: 1280, idealHeight: 720)
    }
}

#Preview {
    PlayerView(
        channelURL: URL(string: "http://localhost:8411/stream/channel/1")!,
        channelName: "Test Channel"
    )
    .frame(width: 800, height: 450)
}
