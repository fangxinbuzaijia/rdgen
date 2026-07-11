# 中文增强版功能状态

## 已接入页面和配置生成

- 中文主页面、等待页、成功页、失败页
- 保存/加载 JSON 配置
- 平台多选批量构建：Windows 64 位、Windows 32 位、Linux、Android、macOS
- 每个平台使用独立 UUID、Actions 运行记录、状态和下载目录，批次页统一展示进度与产物
- 自定义服务器、Key、API、门户网站、下载链接、公司名
- 自定义应用名、文件名、Android 包名
- 图标、Logo、隐私屏幕图片上传和预览
- 主题、图像质量、帧率、视口、显示样式、界面模式
- 认证方式、预设密码、配置 PIN、密码策略
- 权限预设和各项权限开关
- 常见隐藏项、会话行为、连接增强项
- 手动 default-settings / override-settings

## 已改善的部署和安全问题

- Docker Compose 改为构建当前源码，避免继续使用上游英文镜像
- SQLite 数据库持久化到 `./data/db.sqlite3`
- 容器启动时自动执行 `python manage.py migrate`
- GitHub workflow dispatch 的 204 空响应兼容处理
- 成品回传 `/save_custom_client` 增加 Bearer token 校验
- 临时 zip 清理 `/cleanzip` 增加 Bearer token 校验，相关 workflows 已补 Authorization header
- 构建状态回调 `/updategh` 增加 Bearer token 校验和状态白名单
- secrets zip 下载 `/get_zip` 增加 HMAC token 校验，workflow 下载时自动携带 token
- 全站恢复 Django CSRF 防护，仅对 GitHub Actions 回调接口做豁免
- `ALLOWED_HOSTS` 和 `CSRF_TRUSTED_ORIGINS` 默认绑定 `rdgen.920813.xyz`
- 关键环境变量缺失时直接启动失败，避免公网使用 insecure 默认值
- 临时 secrets zip 文件名包含构建 UUID，`/cleanzip` 可以正确清理
- 下载和图片接口对文件名做 `basename` 处理，降低路径穿越风险
- 下载接口要求构建状态为 success，成功页只展示真实存在的文件
- Logo、图标、隐私图片均校验 PNG 格式，图标额外要求正方形
- 主页面增加基础/高级模式和提交前配置摘要

## 仍需逐版本验证的源码级补丁

下面这些功能已经在页面和后端作为 Actions 环境变量传递，但不同 RustDesk 版本源码路径和代码片段可能变化，建议先从 Windows 64 位正式版验证，再逐项扩展 workflow 的 `sed` patch：

- 添加复制按钮
- 禁用安装入口
- 不创建卸载快捷方式
- 禁止被控端退出隐私模式
- 隐藏聊天与语音功能
- 隐藏“技术支持”标识

上游 rdgen 已经有 workflow patch 的功能：

- 顶部显示器切换按钮 `cycleMonitor`
- 地址簿离线标记 `xOffline`
- 隐藏新版本通知 `removeNewVersionNotif`

## 建议上线顺序

1. 先部署中文增强页面。
2. 用 Windows 64 位、RustDesk 正式版本生成一次最小配置客户端。
3. 验证 GitHub Actions 启动、状态刷新、成品回传、下载。
4. 再逐步打开高级设置和源码补丁选项。
5. 对每个 RustDesk 版本保留一份成功配置 JSON，方便回滚。
