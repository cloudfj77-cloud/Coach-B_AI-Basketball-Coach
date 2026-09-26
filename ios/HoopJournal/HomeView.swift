import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

struct PickedMovie: Transferable {
    let url: URL
    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(importedContentType: .movie) { received in
            let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".mov")
            try FileManager.default.copyItem(at: received.file, to: file)
            return PickedMovie(url: file)
        }
    }
}

struct HomeView: View {
    @EnvironmentObject var journal: Journal
    @State private var settings = false
    @State private var upload = false
    private var attempts: Int { journal.trainings.reduce(0) { $0 + $1.stats.attempts } }
    private var made: Int { journal.trainings.reduce(0) { $0 + $1.stats.made } }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("付杰 · 蓝色球衣").font(.subheadline).foregroundStyle(.secondary)
                            Text("每一次出手，\n都有进步的线索。").font(.title2.bold())
                        }
                        Spacer()
                        Text("02").font(.system(size: 70, weight: .black, design: .rounded)).foregroundStyle(.orange)
                    }
                    HStack(spacing: 12) {
                        StatCard(value: "\(journal.trainings.count)", label: "训练记录")
                        StatCard(value: "\(attempts)", label: "已核对出手")
                        StatCard(value: attempts == 0 ? "—" : String(format: "%.1f%%", Double(made)/Double(attempts)*100), label: "命中率")
                    }
                    Button { upload = true } label: {
                        Label("从相册开始新训练", systemImage: "plus.circle.fill").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 10)
                    }.buttonStyle(.borderedProminent).disabled(!journal.configured)
                    if journal.usesMac {
                        Label("Mac 免费模式 · 电脑需开机，设备需在同一网络", systemImage: "desktopcomputer")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    if !journal.configured {
                        VStack(alignment: .leading, spacing: 10) {
                            Label("连接你的训练空间", systemImage: "cloud").font(.headline)
                            Text("连接自己的 Mac 或云端服务后，直接选取手机视频。使用 Mac 时，电脑需要保持开机并与手机联网。").font(.subheadline).foregroundStyle(.secondary)
                            Button("配置服务") { settings = true }
                        }.padding().background(.quaternary, in: RoundedRectangle(cornerRadius: 18))
                    }
                    HStack { Text("训练日志").font(.title2.bold()); Spacer(); if journal.loading { ProgressView() } }
                    if journal.trainings.isEmpty {
                        ContentUnavailableView("从第一段训练开始", systemImage: "basketball", description: Text("视频、逐球数据和复盘会集中保存在这里。"))
                    }
                    ForEach(journal.trainings) { training in
                        NavigationLink { TrainingView(id: training.id) } label: {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack { Text(training.title).font(.headline); Spacer(); Image(systemName: "chevron.right") }
                                Text("\(training.date) · 视频 \(timestamp(training.duration))").font(.caption).foregroundStyle(.secondary)
                                HStack { Text("\(training.stats.made) / \(training.stats.attempts) 命中"); Spacer(); Text(training.stats.rate).font(.title3.bold()).foregroundStyle(.orange) }
                                if training.busy { Label(training.status, systemImage: "hourglass").font(.caption) }
                                else if training.stats.pending > 0 { Text("还有 \(training.stats.pending) 球待核对").font(.caption).foregroundStyle(.orange) }
                            }.padding(18).background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20))
                        }.buttonStyle(.plain)
                    }
                    Text("按已核对出手统计 · 不把看不清的球算作未命中").font(.caption).foregroundStyle(.secondary)
                }.padding(20)
            }.background(Color(.systemGroupedBackground))
                .navigationTitle("Coach B")
                .toolbar { Button { settings = true } label: { Image(systemName: "gearshape") } }
                .refreshable { await journal.fetch() }
                .task { await journal.fetch() }
                .sheet(isPresented: $settings) { SettingsView() }
                .sheet(isPresented: $upload) { UploadView() }
                .alert("暂时无法完成", isPresented: Binding(get: { journal.error != nil }, set: { if !$0 { journal.error = nil } })) { Button("知道了") { journal.error = nil } } message: { Text(journal.error ?? "") }
        }
    }
}

struct StatCard: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) { Text(value).font(.title3.bold()).minimumScaleFactor(0.6).lineLimit(1); Text(label).font(.caption).foregroundStyle(.secondary) }
            .frame(maxWidth: .infinity, alignment: .leading).padding(12).background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
    }
}

struct SettingsView: View {
    @EnvironmentObject var journal: Journal
    @Environment(\.dismiss) var dismiss
    @State private var url = ""
    @State private var token = ""
    @State private var error: String?
    var body: some View {
        NavigationStack {
            Form {
                Section("个人训练服务") {
                    TextField("https://你的服务地址", text: $url).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("访问令牌", text: $token).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Text("访问令牌保存在 iPhone 钥匙串。AI 密钥只配置在服务器，不需要填到这里。").font(.caption)
                }
                Section("第一版说明") {
                    Text(journal.usesMac ? "视频加密传给你的 Mac。电脑需要开机、不休眠，手机与电脑需在同一网络。免费模式先手动核对投篮，再统计命中率、生成集锦和基础建议。" : "视频通过 HTTPS 上传至你的服务。AI 分析需要服务器配置 OpenAI，识别前会再次提示；有疑问的出手需要人工核对。")
                    Text("当前版本上传期间需要保持 App 在前台；上传完成后可以离开，服务器继续处理。")
                }
                if let error { Text(error).foregroundStyle(.red) }
            }.navigationTitle("连接训练空间").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("取消") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) { Button("保存") {
                        do { try journal.settings(url: url, key: token); Task { await journal.fetch() }; dismiss() }
                        catch { self.error = error.localizedDescription }
                    }.disabled(url.isEmpty || token.isEmpty) }
                }.onAppear { url = journal.server; token = journal.token }
        }
    }
}

struct UploadView: View {
    @EnvironmentObject var journal: Journal
    @Environment(\.dismiss) var dismiss
    @State private var selection: PhotosPickerItem?
    @State private var movie: PickedMovie?
    @State private var title = "篮球训练"
    @State private var date = Date()
    @State private var busy = false
    @State private var status = ""
    @State private var error: String?
    var body: some View {
        NavigationStack {
            Form {
                Section("这次练了什么") {
                    TextField("训练名称", text: $title)
                    DatePicker("训练日期", selection: $date, displayedComponents: .date)
                    Label("蓝色 2 号 · 付杰", systemImage: "person.crop.square")
                }
                Section {
                    PhotosPicker(selection: $selection, matching: .videos) { Label(movie == nil ? "从相册选择视频" : "已选视频，点此更换", systemImage: "photo.on.rectangle") }.disabled(busy)
                    Text("支持 2 GB 以内、最长两小时的视频。只读取你选中的视频。").font(.caption)
                }
                if busy { HStack { ProgressView(); Text(status) }; Text(journal.usesMac ? "上传完成前请保持 App 在前台。完成后 Mac 会继续处理，请保持电脑开机。" : "上传完成前请保持 App 在前台。完成后可以离开，服务会继续处理。").font(.caption) }
                if let error { Text(error).foregroundStyle(.red) }
                Button("上传并建立训练记录") {
                    guard let movie else { return }
                    busy = true; status = "正在上传视频…"; error = nil
                    Task {
                        do {
                            _ = try await journal.upload(file: movie.url, title: title, date: date)
                            try? FileManager.default.removeItem(at: movie.url)
                            self.movie = nil; dismiss()
                        } catch { self.error = error.localizedDescription }
                        busy = false
                    }
                }.disabled(movie == nil || busy).font(.headline)
            }.navigationTitle("新训练").navigationBarTitleDisplayMode(.inline)
                .interactiveDismissDisabled(busy)
                .toolbar { Button("关闭") { dismiss() }.disabled(busy) }
                .onChange(of: selection) { _, item in
                    guard let item else { return }
                    busy = true; status = "正在从相册读取…"; error = nil
                    Task {
                        do {
                            let picked = try await item.loadTransferable(type: PickedMovie.self)
                            guard let picked else { throw APIError.message("无法读取该视频") }
                            if let old = movie { try? FileManager.default.removeItem(at: old.url) }
                            movie = picked
                        } catch { self.error = error.localizedDescription }
                        busy = false
                    }
                }
                .onDisappear { if let movie { try? FileManager.default.removeItem(at: movie.url) } }
        }
    }
}
