# 2 号训练日志 · iPhone

付杰的个人篮球训练 App。直接选择手机相册视频，建立记录、逐球核对、生成进球集锦，查看复盘和下次计划。手机端采用 SwiftUI，视频服务可独立部署到云端。

**0.1 开发版：尚未部署公网服务或安装到真实 iPhone。** 模拟器版本已编译并启动；后端上传、转码、核对、集锦导出和重启持久化流程通过测试。目前模拟器连接本机开发服务，不是最终云端部署。

GitHub：[cloudfj77-cloud/basketball-journal](https://github.com/cloudfj77-cloud/basketball-journal)（私有）。

## 已实现

- 系统相册选取 MOV / MP4，上传到个人服务；上传完成后由服务器继续处理。
- 持久训练日志，视频回看，逐球增加、确认、编辑和删除。
- 命中率仅计算已核对且结果明确的出手，未知结果不算未命中。
- 90° 方向调整，HDR 到 SDR 预览转换。
- 正常速度进球、前三个进球的慢动作和复盘尾卡，输出 MP4；系统分享与相册保存入口。
- 基于确认记录的复盘与通用 60 分钟计划，不虚构动作诊断。
- 可选 OpenAI 画面识别接口，明确提示画面传输后才调用；结果先待核对。真实 API 识别质量尚未验证。
- 首次人工复盘导入脚本：19 次出手、6 次命中。个人视频和记录仅保存在忽略目录，未提交 GitHub。

## 当前限制

- 上传需保持前台；尚无断点续传、后台上传或完成推送。预览先下载再播放。
- AI 每秒两帧抽样会漏检或误判，不能当作完整自动统计。
- 当前导出无声集锦；背影开场、人物缩放、自由倾斜校正及配乐待开发。
- 训练计划为标明来源的规则模板，尚非个性化教练模型；历史趋势图待开发。
- 单人私人令牌鉴权，没有多用户账号或 TestFlight 配置。
- 服务重启会将未完成任务标为中断，支持重试，不自动恢复。
- 真实手机脱离 Mac 使用，还需 HTTPS 云服务、持久磁盘和 Apple 签名。没有购买付费服务。

## 本地开发

需要 Python 3.10+、FFmpeg（libx264 / zscale）、Pillow 和中文字体。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
export FFMPEG_PATH=/absolute/path/to/ffmpeg
export FONT_PATH='/System/Library/Fonts/Hiragino Sans GB.ttc'
python -m server.main
```

默认 `http://127.0.0.1:8765`；开发令牌保存在 `data/.token`，不打印或提交。打开 `ios/HoopJournal.xcodeproj`，运行 iPhone 模拟器，在 App 设置填本机地址与私人令牌。正式版本只接受 HTTPS。

```sh
python -m unittest discover -s tests -v
xcodebuild -project ios/HoopJournal.xcodeproj -scheme HoopJournal \
  -sdk iphonesimulator -configuration Debug -derivedDataPath .build \
  CODE_SIGNING_ALLOWED=NO build
# 新增 Swift 文件后重建工程文件，无需第三方依赖
python3 scripts/create_xcode_project.py
```

[部署与安装](docs/deployment.md) · [产品目标](docs/mobile-mvp.md) · [开发路线](ROADMAP.md) · [开发约定](CONTRIBUTING.md)

普通 Apple ID 与无服务器情况下的[低成本方案评估](docs/cost-options.md)。

## 技术参考

- [Apple PhotosPicker](https://developer.apple.com/documentation/photosui/photospicker)：选取特定相册视频。
- [OpenAI 图像输入](https://developers.openai.com/api/docs/guides/images-vision)与[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)：候选投篮识别。
