# 免费个人 Mac 模式

手机选视频，Mac 在后台保存、转码和剪辑，手机查看结果。无需租云服务器，也不调用付费 AI。投篮先手动标记，命中率按已核对数据计算，建议和计划来自现有规则模板。

## 每次使用

1. Mac 与 iPhone 使用同一个可信 Wi-Fi。也可以先用 iPhone 热点测试；当前 USB 热点测试需要保留数据线，不能据此保证拔线后可用。
2. 在 Mac 双击仓库里的 `Start Coach B.command`，保持该窗口打开。服务运行时会阻止空闲休眠；不要合盖、关机或断开网络。
3. 手机打开 Coach B。如果首次弹出本地网络权限，选择允许。下拉刷新能看到旧训练记录，说明连接成功。
4. 从相册选视频并上传。上传期间保持 App 前台；之后 Mac 继续处理。先试短视频，再处理完整训练。
5. 回看视频、手动标记出手和结果，然后查看统计、基础复盘或生成进球集锦。

关闭服务窗口或按 Control-C 停止服务，不删除记录。视频、数据库、令牌与本地证书都在被 Git 忽略的 `data/` 目录。不要删除这个目录来“重置”服务。

## 首次设置（开发者）

需要安装 Pillow 的 Python，以及带 libx264 / zscale 的 FFmpeg。运行：

```sh
python3 scripts/run_local.py --python /path/to/python3 --ffmpeg /path/to/ffmpeg \
  --name YOUR-MAC.local --bind 0.0.0.0 --prepare-only
python3 scripts/run_local.py
```

也可用当前局域网 IP 作为 `--name` 和 `--bind`。IP 随热点或 Wi-Fi 变化时，需要重新配置；脚本不会自动猜测要连接哪张网络。不能填写公网地址或在路由器映射端口。

用个人 Apple 团队构建并安装 Debug 版本，然后在 iPhone 解锁、USB 连接期间运行：

```sh
python3 scripts/connect_iphone.py --device YOUR_DEVICE_ID
```

脚本经 USB 传递服务地址、令牌和证书，不打印密钥，也不把它们编译到 App。令牌保存在手机钥匙串，地址与公开证书保存在 App 设置，重开 App 无需再接 USB。证书有效期一年；需要更换证书时，在 Mac 删除 `data/local/server.pem` 后重新准备并通过 USB 配对，保留其他数据。

连接使用 HTTPS。仅 Debug 版本支持这个专用证书：必须匹配预先配对的主机和完整证书，并通过系统的主机名、有效期等 TLS 检查。不会关闭系统证书校验，也不会在手机安装全局根证书。Release 仍使用普通系统 HTTPS 信任。

启动器明确移除 `OPENAI_API_KEY`，即使终端有该变量也不会调用付费识别。原生 App 的普通 Apple ID 签名仍受有效期限制，需要按时重新签名安装。

## 检查连接信任

服务运行时，可以用 `tests/local_tls_probe.swift` 配合 `LocalServerTrust.swift` 编译运行，验证已配对证书成功，而错误主机、错误证书及未配对连接被拒绝。没有令牌的请求应返回 401；不应放宽鉴权来排查网络。

## 验证进度

- 已有真实 iPhone 安装、手动启动确认。
- 已验证手机热点下真机经 HTTPS 读取已有训练记录；TLS 配对校验及后端上传、转码、剪辑、持久化测试通过。
- 已收到手机相册上传的 20 分 47 秒、约 1.66 GB 视频，并完成初次转码与画面旋转后的重新处理。
- 手机回看与拔线使用仍需逐项验收，上传成功不代表这些步骤已经完成。
- 尚无不依赖 Mac 的免费自动视频识别；当前不承诺 AI 命中率或动作诊断。
