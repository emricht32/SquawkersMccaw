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
                        viewModel.sendSelectedSong(name)
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
//            .refreshable {
//                viewModel.songDisplayNames.removeAll()
//            }
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
