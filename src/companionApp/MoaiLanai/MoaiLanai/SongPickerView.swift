//
//  SongPickerView.swift
//  MoaiLanai
//
//  Created by Jon Emrich on 5/12/25.
//


import SwiftUI

struct SongPickerView: View {
    @ObservedObject private var viewModel: BirdPiViewModel
    
    init(viewModel: BirdPiViewModel = BirdPiViewModel()) {
        self.viewModel = viewModel
    }

    var body: some View {
        NavigationView {
            List {
                ForEach(Array(viewModel.songDisplayNames.enumerated()), id: \.offset) { index, name in
                    HStack {
                        Text("\(index + 1))  \(name)")
                        Spacer()
                        if viewModel.selectedIndex == index {
                            Image(systemName: "checkmark")
                                .foregroundColor(.green)
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        viewModel.sendSelectedSongIndex(index)
                    }
                }
            }
            .navigationTitle("Select a Song")
            .refreshable {
                viewModel.songDisplayNames.removeAll()
                viewModel.sendSelectedSongIndex(-1)
            }
            .overlay {
                if !viewModel.isConnected {
                    ProgressView("Connecting to BirdPi...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(Color(.systemBackground).opacity(0.85))
                }
            }
        }
    }
}

#Preview {
    SongPickerView(
        viewModel: .init(
            songNames: [
                "In The Tiki Room",
                "The Seasons Upon Us",
                "Wellerman",
                "Mele-Kalikimaka",
                "Lets Get It Started",
                "Happy Birthday",
                "Jack Sparrow",
                "Beverly Hills"
            ]
        )
    )
}
