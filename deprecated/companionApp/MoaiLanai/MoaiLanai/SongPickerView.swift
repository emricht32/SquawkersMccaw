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
                ForEach(Array(viewModel.songs.enumerated()), id: \.offset) { index, song in
                    HStack {
                        Text("\(index + 1))  \(song.name)")
                        Spacer()
                        if song.state == .playing {
                            Image(systemName: "checkmark")
                                .foregroundColor(.green)
                        } else if song.state == .reqesting {
                            ProgressView()
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        viewModel.sendSelected(song)
                    }
                }
            }
            .navigationTitle("Select a Song")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        viewModel.toggleSortState()
                    }) {
                        switch viewModel.sortState {
                        case .unsorted:
                            Image(systemName: "line.3.horizontal")
                        case .ascending:
                            Image(systemName: "arrow.up")
                        case .descending:
                            Image(systemName: "arrow.down")
                        }
                    }
                    .accessibilityLabel("Sort Songs")
                }
            }
            .overlay {
                if !viewModel.isConnected && viewModel.songs.isEmpty {
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
            songs: [
                Song(name: "In The Tiki Room", index: 0),
                Song(name: "The Seasons Upon Us",index: 1),
                Song(name: "Wellerman",index: 2),
                Song(name: "Mele-Kalikimaka",index: 3),
                Song(name: "Lets Get It Started",index: 4),
                Song(name: "Happy Birthday",index: 5),
                Song(name: "Jack Sparrow",index: 6),
                Song(name: "Beverly Hills",index: 7)
            ]
        )
    )
}
