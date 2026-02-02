//
//  AboutView.swift
//  EXStreamTVApp
//
//  About window view.
//

import SwiftUI

struct AboutView: View {
    var body: some View {
        VStack(spacing: 16) {
            // App Icon
            Image(systemName: "tv.fill")
                .font(.system(size: 64))
                .foregroundStyle(
                    LinearGradient(
                        colors: [.blue, .purple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
            
            // App Name
            Text("EXStreamTV")
                .font(.title)
                .fontWeight(.bold)
            
            // Version
            Text("Version 1.4.0")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Divider()
                .padding(.horizontal, 40)
            
            // Description
            Text("Unified IPTV Streaming Platform")
                .font(.subheadline)
            
            Text("Combining the best of StreamTV and ErsatzTV")
                .font(.caption)
                .foregroundColor(.secondary)
            
            Spacer()
            
            // Links
            HStack(spacing: 20) {
                Button("Website") {
                    openURL("https://github.com/exstreamtv")
                }
                .buttonStyle(.link)
                
                Button("Documentation") {
                    openURL("https://github.com/exstreamtv/docs")
                }
                .buttonStyle(.link)
                
                Button("Report Issue") {
                    openURL("https://github.com/exstreamtv/issues")
                }
                .buttonStyle(.link)
            }
            .font(.caption)
            
            // Copyright
            Text("© 2026 EXStreamTV. MIT License.")
                .font(.caption2)
                .foregroundColor(.secondary)
                .padding(.top, 8)
        }
        .padding(30)
        .frame(width: 400, height: 350)
    }
    
    private func openURL(_ urlString: String) {
        if let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}

#Preview {
    AboutView()
}
