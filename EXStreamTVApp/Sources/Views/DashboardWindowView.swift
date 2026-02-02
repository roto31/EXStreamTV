//
//  DashboardWindowView.swift
//  EXStreamTVApp
//
//  Native dashboard window view with embedded WebView.
//

import SwiftUI
import WebKit

struct DashboardWindowView: View {
    @EnvironmentObject var serverManager: ServerManager
    @EnvironmentObject var channelManager: ChannelManager
    
    var body: some View {
        Group {
            if serverManager.isRunning {
                WebView(url: URL(string: "http://localhost:\(serverManager.port)/dashboard")!)
            } else {
                ServerOfflineView()
            }
        }
        .frame(minWidth: 800, minHeight: 600)
        .toolbar {
            ToolbarItemGroup(placement: .navigation) {
                Button(action: { refreshPage() }) {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Refresh")
            }
            
            ToolbarItemGroup(placement: .primaryAction) {
                ServerStatusBadge()
                
                Button(action: { openInBrowser() }) {
                    Image(systemName: "safari")
                }
                .help("Open in Browser")
            }
        }
    }
    
    private func refreshPage() {
        // Would refresh the WebView
        NotificationCenter.default.post(name: .refreshWebView, object: nil)
    }
    
    private func openInBrowser() {
        if let url = URL(string: "http://localhost:\(serverManager.port)/dashboard") {
            NSWorkspace.shared.open(url)
        }
    }
}

// MARK: - Server Status Badge

struct ServerStatusBadge: View {
    @EnvironmentObject var serverManager: ServerManager
    
    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(serverManager.isRunning ? .green : .gray)
                .frame(width: 8, height: 8)
            
            Text(serverManager.isRunning ? "Online" : "Offline")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(4)
    }
}

// MARK: - Server Offline View

struct ServerOfflineView: View {
    @EnvironmentObject var serverManager: ServerManager
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "server.rack")
                .font(.system(size: 64))
                .foregroundColor(.secondary)
            
            Text("Server Offline")
                .font(.title)
                .fontWeight(.bold)
            
            Text("The EXStreamTV server is not running.\nStart the server to view the dashboard.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            if serverManager.isStarting {
                ProgressView("Starting server...")
            } else {
                Button(action: {
                    Task { await serverManager.start() }
                }) {
                    Label("Start Server", systemImage: "play.fill")
                        .frame(width: 150)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
            
            if let error = serverManager.lastError {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.top)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// MARK: - WebView

struct WebView: NSViewRepresentable {
    let url: URL
    
    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.preferences.javaScriptEnabled = true
        
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.load(URLRequest(url: url))
        
        // Register for refresh notifications
        NotificationCenter.default.addObserver(
            forName: .refreshWebView,
            object: nil,
            queue: .main
        ) { _ in
            webView.reload()
        }
        
        return webView
    }
    
    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Update URL if changed
        if nsView.url != url {
            nsView.load(URLRequest(url: url))
        }
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("WebView navigation failed: \(error.localizedDescription)")
        }
        
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            print("WebView provisional navigation failed: \(error.localizedDescription)")
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let refreshWebView = Notification.Name("refreshWebView")
}

// MARK: - Preview

#Preview {
    DashboardWindowView()
        .environmentObject(ServerManager())
        .environmentObject(ChannelManager())
}
