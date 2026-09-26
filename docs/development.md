# Coach B 开发指南

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

## 技术参考

- [Apple PhotosPicker](https://developer.apple.com/documentation/photosui/photospicker)：选取特定相册视频。
- [OpenAI 图像输入](https://developers.openai.com/api/docs/guides/images-vision)与[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)：候选投篮识别。


更多：[部署与安装](deployment.md) · [贡献约定](../CONTRIBUTING.md)
