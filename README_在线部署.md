# 在线版部署（Render / Railway）

在线版包含一个 Python 服务：

- 托管整个网站；
- `/api/state` 保存共享数据（`data/online_state.json`）；
- `/api/events` 通过 SSE 把修改实时推送给所有打开页面的人。

## Render 部署步骤

1. 把整个 `项目管理网站` 文件夹上传到 GitHub 仓库（私有也可以）。
2. 打开 https://render.com → New → Web Service → 连接该仓库。
3. 配置：
   - Runtime：Python
   - Build Command：留空
   - Start Command：`python tools/online_server.py`
   - 环境变量：`EDIT_TOKEN` = 你的编辑口令（可选，建议设置）
4. 部署完成后得到公网网址，例如 `https://xxx.onrender.com`。

## Railway 部署

- New Project → Deploy from GitHub，选择仓库。
- 启动命令：`python tools/online_server.py`（或使用仓库中的 Dockerfile）。
- 设置环境变量 `EDIT_TOKEN`。

## 编辑与查看

- 你本人：打开 `https://你的网址/?edit=你的EDIT_TOKEN`，之后可正常编辑；口令会保存在本浏览器。
- 其他人：直接打开 `https://你的网址/`，只读查看；你保存后页面会自动刷新显示最新数据。
- 未设置 `EDIT_TOKEN` 时任何人都能编辑，正式使用建议设置。

## 数据持久化

- 默认数据保存在 `data/online_state.json`。
- Render 免费实例重启/重新部署后文件可能丢失。要永久保存，请挂载持久磁盘（Render Disk / Railway Volume），并设置环境变量：
  `STATE_FILE=/var/data/online_state.json`
- 首次启动若没有状态文件，会尝试从 `data/local_overrides.js` 读取现有数据作为初始内容。

## 说明

- 实时同步依赖浏览器支持 SSE（Chrome/Edge/Firefox 均支持）。
- 两位编辑者同时修改时以最后保存的数据为准，其他页面会自动刷新。