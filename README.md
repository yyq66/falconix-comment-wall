# 实时评论墙

鹰眼智能 2027 校园招聘代码考核。基于随题 Figma 原型，使用 Vue 3 + TypeScript + FastAPI，提供可以实际多人协作的便签墙。

## 快速体验

在线地址：完成托管平台配置后补充。源码及自动检查保存在私有仓库 `yyq66/falconix-comment-wall`。

| 演示账号 | 显示名称 | 默认密码 |
| --- | --- | --- |
| `demo_a` | 赵欣 | `Wall2027!` |
| `demo_b` | 王美丽 | `Wall2027!` |

用普通窗口和无痕窗口，或两个不同浏览器，分别登录两个账号。同一浏览器普通标签页共享登录 Cookie，不能当作两个独立账号。

1. 选择「新增」，点击画布空白位置，在弹窗中输入并发表。
2. 在鼠标选择模式下点击自己的贴纸编辑；点击他人的贴纸只能查看。
3. 选择「拖动」，拖动自己的贴纸；聚焦自己的卡片后也可用方向键移动。
4. 直接点击贴纸内爱心点赞，再点一次取消。其他用户无需刷新即可看到变化。
5. 「智能整理」将个人视图按情绪分列，再点「还原布局」恢复原始位置。

不提供注册。首次放入八条原型评论，在线成员来自真实连接，总数与情绪占比实时计算。手机可左右滑动浏览画布。

## 功能范围

- 账号密码登录、自动登录、密码显示切换、错误提示和退出。
- 自由定位便签；加粗、斜体、下划线、删除线、有序和无序列表。
- 创建、编辑、移动位置和点赞持久化。
- 服务端作者权限；他人只能查看和点赞。每人每条最多一个赞，允许自赞和取消。
- WebSocket 同步新增、编辑、最终移动位置、点赞和在线成员。
- 同账号多标签页去重、心跳、断网反馈、重连和完整状态恢复。
- 根据内容自动变色、情绪占比、可还原的个人分类布局。
- 头像和图标来自题目文件，来源记录在 `frontend/public/assets/manifest.json`。

## 本地运行

需要 Python 3.13 和 Node.js 24，在项目根目录执行：

```sh
python -m venv .venv
```

Windows 激活 `.venv\Scripts\activate`，macOS/Linux 执行 `source .venv/bin/activate`，然后：

```sh
pip install -r requirements.lock
cd frontend
npm ci
npm run build
cd ..
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 。本地不设置 `DATABASE_URL` 时使用 `data/wall.db`，关闭并重新启动不会丢失数据。

开发时后端增加 `--reload`，另在 `frontend` 执行 `npm run dev`，访问 http://127.0.0.1:5173。Vite 会代理接口和实时连接。

`.env` 可从 `.env.example` 复制，启动时增加 `--env-file .env`。不要提交实际数据库连接字符串。

## 免费部署

推荐 Render 免费 Web Service + Neon 免费 PostgreSQL，使用一个 HTTPS 地址。仓库提供生产 `Dockerfile` 和 `render.yaml`。

| 环境变量 | 作用 |
| --- | --- |
| `DATABASE_URL` | Neon PostgreSQL 连接字符串，作为秘密保存 |
| `COOKIE_SECURE=1` | HTTPS 下使用安全 Cookie |
| `APP_ENV=production` | 缺少外部数据库时拒绝启动，避免临时磁盘丢数据 |
| `SEED_DEMO=1` | 首次加入演示评论，后续不重复插入或覆盖 |
| `DEMO_PASSWORD` | 可选，仅首次创建用户时生效；登录页快捷填入使用默认密码 |

详细操作和线上验收见[部署说明](docs/deployment.md)。免费应用可能休眠，首次打开约需一分钟；生产环境必须使用外部数据库。

## 测试

```sh
python -m unittest discover -s tests -v
cd frontend
npm run build
```

本地无 PostgreSQL 时跳过一项专门集成测试；设置独立的 `TEST_DATABASE_URL` 后运行，不要指向需要保留数据的环境。

启动应用后执行完整浏览器回归：

```sh
npx --yes --package @playwright/cli@0.1.25 playwright-cli -s=wall open http://127.0.0.1:8000
npx --yes --package @playwright/cli@0.1.25 playwright-cli -s=wall run-code --filename=scripts/browser-check.js
```

该流程实际操作两个用户，覆盖错误登录、六种富文本格式、内容编辑、权限、点赞、拖动、实时同步、断网补齐、多标签页及七个响应式断点。它会创建少量带“验收”标记的评论，请在测试或演示环境执行。

GitHub 自动检查运行后端测试、真实 PostgreSQL 集成、前端构建、生产容器构建和启动，并对容器执行双用户浏览器回归。分阶段提交和失败修复见[开发记录](docs/development.md)。

## 实现与取舍

- **一致性**：数据库为最终状态来源，成功保存后推送完整快照。连接注册、HTTP 快照和数据修改共用变更锁，客户端按递增版本接收状态。
- **冲突处理**：正文和位置使用独立版本，过期修改返回 409；移动不会覆盖正文。创建按请求标识去重；点赞使用复合主键和目标状态，重试不会多加。
- **权限与内容**：后端校验作者；Cookie 为 HttpOnly/SameSite，写请求与 WebSocket 校验 Origin。密码使用 bcrypt，会话只保存 Token 哈希。富文本采用标签白名单，移除脚本和属性。
- **在线状态**：单进程维护连接，按用户去重；心跳检查失效连接，重连重新获取状态，退出撤销会话和连接。
- **情绪分析**：本地中文词组、否定和转折规则，无外部模型或密钥依赖。反讽、复杂混合表达可能误判，规则在 `backend/sentiment.py`。
- **智能整理**：仅改变个人视图，按实际卡片高度排列，不改他人坐标；选择新增或拖动工具会退出整理视图。
- **规模边界**：面向单实例考核演示，推送完整快照；最多 1000 条评论，单条 1000 字。正文并发编辑提示版本冲突，拖动松手后同步最终位置。不提供删除、多房间、短信或注册。

## 目录

```text
backend/                  Python 服务、鉴权、数据、同步与情绪规则
frontend/                 Vue 界面与原型素材
tests/                    后端与 PostgreSQL 回归
scripts/browser-check.js  双用户浏览器验收
docs/                     开发与部署说明
Dockerfile                单服务生产镜像
render.yaml               免费托管配置
```
