import SwiftUI
import AVKit
import Photos

struct TrainingView: View {
    @EnvironmentObject var journal: Journal
    let id: String
    @State private var player: AVPlayer?
    @State private var playerRevision = -1
    @State private var edited: Shot?
    @State private var working = false
    @State private var aiConfirmation = false
    @State private var tab = 0
    @State private var export: URL?
    @State private var notice: String?
    private var training: Training? { journal.trainings.first { $0.id == id } }

    var body: some View {
        Group {
            if let training {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        if let player { VideoPlayer(player: player).frame(height: 220).clipShape(RoundedRectangle(cornerRadius: 18)) }
                        else if training.previewReady { Button("加载视频以回看") { load(training) } }
                        else { RoundedRectangle(cornerRadius: 18).fill(.quaternary).frame(height: 180).overlay { Label("正在准备视频", systemImage: "video") } }
                        HStack { StatCard(value: "\(training.stats.attempts)", label: "已核对出手"); StatCard(value: "\(training.stats.made)", label: "命中"); StatCard(value: training.stats.rate, label: "命中率") }
                        if training.busy || working { HStack { ProgressView(); Text(training.busy ? training.status : "正在处理…").font(.subheadline) } }
                        if !training.error.isEmpty { Text(training.error).font(.subheadline).foregroundStyle(.red) }
                        if !training.previewReady && !training.busy { Button("重新准备视频") { action(training, "prepare") } }
                        Picker("内容", selection: $tab) { Text("逐球核对").tag(0); Text("复盘与计划").tag(1); Text("分享集锦").tag(2) }.pickerStyle(.segmented)
                        if tab == 0 { shots(training) }
                        if tab == 1 {
                            Text(training.report).font(.body).textSelection(.enabled).lineSpacing(6)
                            ShareLink(item: training.report) { Label("分享文字复盘", systemImage: "square.and.arrow.up") }
                        }
                        if tab == 2 { highlights(training) }
                    }.padding(20)
                }.navigationTitle(training.title).navigationBarTitleDisplayMode(.inline)
                    .refreshable { await journal.fetch() }
            } else { ContentUnavailableView("暂时找不到记录", systemImage: "basketball") }
        }
        .task {
            if let training, training.previewReady { load(training) }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(4))
                guard !Task.isCancelled else { break }
                if training?.busy == true {
                    await journal.fetch()
                    if let training, !training.busy, training.previewReady, playerRevision != training.turns { load(training) }
                }
            }
        }
        .onDisappear { player?.pause() }
        .sheet(item: $edited) { shot in
            if let training { ShotEditor(shot: shot, duration: training.duration) { changed in
                var shots = training.shots
                if let index = shots.firstIndex(where: { $0.id == changed.id }) { shots[index] = changed } else { shots.append(changed) }
                try await journal.saveShots(shots, for: training)
            } }
        }
        .confirmationDialog("开始 AI 视频识别？", isPresented: $aiConfirmation, titleVisibility: .visible) {
            Button("发送画面并开始识别") { if let training { action(training, "analyze") } }
        } message: { Text("服务器会将抽取的视频画面发送至 OpenAI，并使用服务器配置的 API 额度。识别结果先标记为待核对，不直接计入命中率。") }
        .alert("提示", isPresented: Binding(get: { notice != nil }, set: { if !$0 { notice = nil } })) { Button("知道了") { notice = nil } } message: { Text(notice ?? "") }
    }

    @ViewBuilder private func shots(_ training: Training) -> some View {
        Text("\(training.stats.pending) 球待核对 · 播放到出手瞬间可手动补记").font(.caption).foregroundStyle(.secondary)
        HStack {
            Button { aiConfirmation = true } label: { Label("AI 找出投篮", systemImage: "sparkles") }.disabled(!training.aiAvailable)
            Spacer()
            Button("画面转 90°") { action(training, "rotate") }
        }.disabled(training.busy || working || !training.previewReady)
        if !training.aiAvailable { Text("AI 服务尚未配置，可以先手动标记与剪辑。").font(.caption).foregroundStyle(.secondary) }
        Button {
            guard let player else { return }
            player.pause()
            let current = player.currentTime().seconds
            let time = current.isFinite ? min(max(0, current), max(0, training.duration-0.1)) : 0
            edited = Shot(start: max(0, time-2), release: time, end: min(training.duration, time+3))
        } label: { Label("标记当前出手", systemImage: "plus.circle") }.buttonStyle(.borderedProminent).disabled(player == nil || training.busy || working)
        if training.shots.isEmpty { Text("尚无投篮记录。先识别或手动标记，再核对每球的命中结果。").foregroundStyle(.secondary).padding(.vertical) }
        ForEach(training.shots) { shot in
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Button { player?.seek(to: CMTime(seconds: shot.start, preferredTimescale: 600)); player?.play() } label: { Label(timestamp(shot.release), systemImage: "play.circle.fill") }
                    Spacer()
                    Text(shot.label).font(.subheadline.bold()).foregroundStyle(shot.reviewed ? Color.primary : Color.orange)
                    Menu {
                        Button("核对 / 编辑") { player?.pause(); edited = shot }
                        Button("删除误识别", role: .destructive) {
                            working = true
                            Task { do { try await journal.saveShots(training.shots.filter { $0.id != shot.id }, for: training) } catch { notice = error.localizedDescription }; working = false }
                        }
                    } label: { Image(systemName: "ellipsis.circle") }.disabled(training.busy || working)
                }
                if !shot.note.isEmpty { Text(shot.note).font(.caption).foregroundStyle(.secondary) }
                if !shot.reviewed { Button("核对这一球") { player?.pause(); edited = shot }.font(.subheadline).disabled(training.busy || working) }
            }.padding().background(.quaternary, in: RoundedRectangle(cornerRadius: 14))
        }
    }

    @ViewBuilder private func highlights(_ training: Training) -> some View {
        Text("正常速度进球 → 精选慢动作 → 数据与复盘尾卡").font(.headline)
        Text("第一版输出无声集锦，保留原片。只剪入已确认进球；画面方向与上方预览保持一致。").font(.subheadline).foregroundStyle(.secondary)
        Button(training.highlightReady ? "重新生成集锦" : "生成进球集锦") { export = nil; action(training, "render") }.buttonStyle(.borderedProminent).disabled(training.stats.made == 0 || training.busy || working)
        if training.highlightStale && training.highlightReady { Text("投篮记录或画面方向已改变，建议重新生成集锦。").font(.caption).foregroundStyle(.orange) }
        if training.highlightReady {
            Button("下载集锦到手机") {
                working = true
                Task { do { export = try await journal.download(training, kind: "highlight") } catch { notice = error.localizedDescription }; working = false }
            }.disabled(working || training.busy)
        }
        if let export {
            ShareLink(item: export) { Label("分享给朋友", systemImage: "square.and.arrow.up") }.buttonStyle(.bordered)
            Button("保存到相册") {
                Task {
                    let permission = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
                    guard permission == .authorized || permission == .limited else { notice = "请在系统设置中允许添加视频到相册"; return }
                    do { try await PHPhotoLibrary.shared().performChanges { PHAssetChangeRequest.creationRequestForAssetFromVideo(atFileURL: export) }; notice = "已保存到相册" }
                    catch { notice = error.localizedDescription }
                }
            }
        }
    }

    private func load(_ training: Training) {
        guard !working else { return }
        working = true
        Task {
            do { let file = try await journal.download(training, kind: "preview"); player?.pause(); player = AVPlayer(url: file); playerRevision = training.turns }
            catch { notice = error.localizedDescription }
            working = false
        }
    }

    private func action(_ training: Training, _ name: String) {
        working = true
        Task { do { try await journal.action(training, name) } catch { notice = error.localizedDescription }; working = false }
    }
}

struct ShotEditor: View {
    @State var shot: Shot
    let duration: Double
    let save: (Shot) async throws -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var error: String?
    var body: some View {
        NavigationStack {
            Form {
                Section("逐球确认") {
                    Picker("结果", selection: $shot.outcome) { Text("命中").tag("made"); Text("未命中").tag("missed"); Text("无法判断").tag("unknown") }
                    Toggle("我已核对原片", isOn: $shot.reviewed)
                }
                Section("片段时间（秒）") {
                    HStack { Text("开始"); Spacer(); TextField("开始", value: $shot.start, format: .number).multilineTextAlignment(.trailing).keyboardType(.decimalPad) }
                    HStack { Text("出手"); Spacer(); TextField("出手", value: $shot.release, format: .number).multilineTextAlignment(.trailing).keyboardType(.decimalPad) }
                    HStack { Text("结束"); Spacer(); TextField("结束", value: $shot.end, format: .number).multilineTextAlignment(.trailing).keyboardType(.decimalPad) }
                    Text("视频总长 \(timestamp(duration))，片段应包含出手与进球结果。").font(.caption)
                }
                Section("观察与不足") { TextField("记录原片中能看见的问题；不确定可留空", text: $shot.note, axis: .vertical).lineLimit(3...8) }
                if let error { Text(error).foregroundStyle(.red) }
            }.navigationTitle("核对投篮").navigationBarTitleDisplayMode(.inline).interactiveDismissDisabled(busy)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("取消") { dismiss() }.disabled(busy) }
                    ToolbarItem(placement: .confirmationAction) { Button("保存") {
                        busy = true
                        Task { do { try await save(shot); dismiss() } catch { self.error = error.localizedDescription }; busy = false }
                    }.disabled(busy) }
                }
        }
    }
}
