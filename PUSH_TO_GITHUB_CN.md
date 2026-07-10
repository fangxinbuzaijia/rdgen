# 更新到 GitHub fork 的方法

目标仓库：

```text
https://github.com/fangxinbuzaijia/rdgen
```

## 方法一：GitHub 网页上传

适合不想在本地配置 Git。

1. 解压 `rdgen-cn-enhanced.zip`。
2. 打开 `https://github.com/fangxinbuzaijia/rdgen`。
3. 建议先创建一个新分支，例如 `cn-enhanced`。
4. 删除仓库里旧的同名文件，再上传解压后的全部文件。
5. 提交信息建议写：

```text
Chinese enhanced rdgen deployment
```

6. 到 Actions 页面确认 workflows 仍然存在。

## 方法二：服务器或本机使用 Git

```bash
git clone https://github.com/fangxinbuzaijia/rdgen.git
cd rdgen
cp -a /path/to/rdgen-cn-enhanced/* .
git add .
git commit -m "Chinese enhanced rdgen deployment"
git push origin master
```

如果你想保留原版 `master`，可以推到新分支：

```bash
git checkout -b cn-enhanced
git add .
git commit -m "Chinese enhanced rdgen deployment"
git push origin cn-enhanced
```

然后服务器 `.env` 里把：

```env
GHBRANCH=cn-enhanced
```

GitHub Actions 也会从这个分支读取 workflow。

## 推送后必须检查

- `Settings -> Secrets and variables -> Actions` 中有 `GENURL` 和 `ZIP_PASSWORD`
- `GENURL=https://rdgen.920813.xyz`
- `ZIP_PASSWORD` 和服务器 `.env` 完全一致
- Actions 已启用
- `GHBEARER` token 对 `fangxinbuzaijia/rdgen` 有 Actions/Workflows 读写权限
