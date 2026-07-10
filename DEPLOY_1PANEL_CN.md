# rdgen.920813.xyz 部署说明（1Panel / Ubuntu）

## 1. GitHub 仓库准备

你的 GitHub 账号：`fangxinbuzaijia`

1. 确认已经 fork `bryangerlach/rdgen` 到 `fangxinbuzaijia/rdgen`。
2. 进入 `https://github.com/fangxinbuzaijia/rdgen/actions`，如果提示启用 Actions，点绿色按钮启用。
3. 创建 fine-grained personal access token：
   - Repository access：只选择 `fangxinbuzaijia/rdgen`
   - Repository permissions：
     - Actions：Read and write
     - Workflows：Read and write
     - Contents：Read
4. 在 `fangxinbuzaijia/rdgen` 的 `Settings -> Secrets and variables -> Actions` 里新增：
   - `GENURL`：`https://rdgen.920813.xyz`
   - `ZIP_PASSWORD`：和服务器 `.env` 里的 `ZIP_PASSWORD` 保持一致

可选签名功能：

- Windows 代码签名：`SIGN_BASE_URL`、`SIGN_API_KEY`
- Android 签名：`ANDROID_SIGNING_KEY`
- macOS 签名：`MACOS_P12_BASE64`

## 2. 1Panel 部署方式

在 1Panel 中创建一个 Docker Compose 应用，项目目录建议：

```bash
/opt/1panel/apps/rdgen/rdgen
```

把本项目文件上传到该目录，然后复制环境变量模板：

```bash
cp .env.example .env
```

生成三个随机密钥：

```bash
openssl rand -hex 64
openssl rand -hex 64
openssl rand -hex 64
```

分别填入 `.env`：

- `SECRET_KEY`
- `ZIP_PASSWORD`
- `CALLBACK_TOKEN`

再填入：

- `GHBEARER`：GitHub fine-grained token
- `GHUSER=fangxinbuzaijia`
- `GENURL=https://rdgen.920813.xyz`
- `REPONAME=rdgen`
- `DB_PATH=/opt/rdgen/data/db.sqlite3`
- `ALLOWED_HOSTS=rdgen.920813.xyz,localhost,127.0.0.1`
- `CSRF_TRUSTED_ORIGINS=https://rdgen.920813.xyz`

启动：

```bash
docker compose up -d
```

## 3. 1Panel 反向代理

在 1Panel 网站里创建反向代理：

- 主域名：`rdgen.920813.xyz`
- 代理地址：`http://127.0.0.1:8022`
- 开启 HTTPS
- 申请 Let's Encrypt 证书
- 如果有上传限制选项，把最大请求体设置为 1024 MB，避免大型安装包回传失败

如果 1Panel 的 OpenResty/Nginx 和 Docker 不在同一网络，也可以把 Compose 端口保持为：

```yaml
ports:
  - "8022:8000"
```

## 4. 首次验证

1. 打开 `https://rdgen.920813.xyz`
2. 填写配置名称，例如 `test_client`
3. 平台先选 `Windows 64Bit`
4. 不填服务器地址、Key、API，确认不会预填你的默认值
5. 提交生成
6. 到 `https://github.com/fangxinbuzaijia/rdgen/actions` 查看 workflow 是否启动
7. 构建完成后回到网页下载

## 5. 常见问题

- GitHub 没有启动 workflow：检查 `GHBEARER` 权限、Actions 是否启用、`GHUSER/REPONAME/GHBRANCH` 是否正确。
- 页面一直等待：检查 Actions 日志是否成功回传文件，检查服务器公网 `GENURL` 是否可访问。
- 上传成品返回 401：检查 `.env` 的 `CALLBACK_TOKEN` 是否传入容器，重新部署后再试。
- `ZIP_PASSWORD` 错误：GitHub secret 和服务器 `.env` 必须完全一致。
- 域名 HTTPS 失败：确认 `rdgen.920813.xyz` 已解析到服务器公网 IP，80/443 端口已放行。
