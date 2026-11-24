# 免费部署与交付

## 线上地址与状态

当前账号下 Render 和 Northflank 均要求绑卡，未继续使用。Hugging Face 当前新建 Docker Space 要求付费会员，也未采用。实际选择 Railway 的免绑卡免费/试用额度方案，数据库继续使用已创建并验证的 Neon 免费 PostgreSQL。

线上地址：**https://comment-wall-production-357fe9fd.up.railway.app** 。2026-11-24 已部署并完成真实公网双用户协作、作者权限和服务重启后的数据保留验证。

Railway 项目为 `falconix-comment-wall`，服务为 `comment-wall`，部署区域为新加坡，单实例。`railway.json` 指定 Docker 构建和数据库健康检查。上传使用官方 CLI，数据库连接串通过标准输入设置为平台变量，不进入源码。当前没有连接 GitHub 自动部署，更新后应手动运行 CLI 上传。

平台控制台：https://railway.com/project/edfc6ef2-1b4b-4980-9333-2cb27fb69914 。控制台需要项目所有者登录，评审直接使用上面的应用地址。

## 账号准备

当前 Railway 和 Neon 授权已完成。账号注册、平台条款及必要的人机验证由账号本人操作，不需要发送密码。

源码仓库采用私有仓库，本次通过官方 CLI 上传，不依赖平台读取私有 GitHub 仓库。若以后连接 GitHub 自动部署，仅授权这个项目。

## 数据库

1. Neon 免费 PostgreSQL 项目 `falconix-comment-wall` 已创建，使用新加坡区域和 PostgreSQL 17。
2. 获取连接字符串，通常形如 `postgresql://…/neondb?sslmode=require`。
3. 连接字符串已写入 Railway 的 `DATABASE_URL` 环境变量，作为秘密保存，不写入 Git。应用使用连接池端点和 TLS。

应用会在首次启动时创建表并放入八条来自题目原型的演示评论。后续重启不重复插入，也不覆盖已保存评论。默认演示密码只用于这份考核演示，不应保存真实公司内部信息。

## 应用

在项目目录使用已登录的 Railway 官方工具：

```sh
railway link --project edfc6ef2-1b4b-4980-9333-2cb27fb69914
railway up --service comment-wall --detach
railway deployment list --service comment-wall --json
railway logs --service comment-wall --lines 50
```

- 构建方式：Docker。
- 账号方案：Trial 免费额度，未绑定银行卡。
- Dockerfile：仓库根目录 `Dockerfile`。
- 环境变量：`DATABASE_URL`、`COOKIE_SECURE=1`、`SEED_DEMO=1`、`APP_ENV=production`。
- `PORT=10000`，公开域名连接到该端口。
- 不增加 `--workers`，在线连接当前由单进程维护。
- 每次功能变更先提交并测试，检查通过后再上传部署。

首次构建完成后生成 Railway 域名；更新部署继续使用同一个地址。必须检查页面、登录、双用户同步与数据保存，不能只看构建成功状态。保留 `render.yaml` 作为替代平台参考，但当前 Render 账号要求绑卡。

## 免费额度与限制

- Railway 当前账号界面显示 **30 天或 $5 用量**，以先耗尽者为准。免费试用结束后按平台当时提供的 Free 方案和账户资格处理；不能保证无限期免费运行。
- 本次没有添加银行卡，也没有选择付费套餐。试用额度耗尽可能停止应用，提交时需要确认额度仍足够。
- 应用本地磁盘不作为长期数据存储，本项目生产配置强制要求外部 PostgreSQL。
- Neon 免费方案受计算、流量和存储额度限制；本项目当前没有外部模型调用费用。
- 平台免费规则会变化，应以创建服务当时显示的免费计划为准。

## 线上验收

两个独立浏览器会话分别登录 `demo_a` 和 `demo_b`（默认密码 `Wall2027!`）：

1. 在线成员互相可见。
2. A 发便签，B 不刷新出现；A 编辑和移动后 B 同步。
3. B 点赞 A 的便签，双方数量同步；重复点赞不会重复计数，可取消。
4. B 只能查看 A 的便签，不能编辑或移动；服务端也拒绝直接越权请求。
5. 刷新、重新登录及服务重新部署后，已保存内容、位置、点赞仍在。
6. 编辑内容会重新分类情绪，占比及时更新；智能整理分列且不写共享位置，可还原。
7. 断开网络再恢复，状态自动补齐；退出后在线列表更新。

可重复的公网专项检查：

```sh
python scripts/online-check.py https://comment-wall-production-357fe9fd.up.railway.app
# 重启后检查之前保存的同一条验收评论
python scripts/online-check.py https://comment-wall-production-357fe9fd.up.railway.app --verify-only
```

首次命令会创建一条带上线验收标记的评论，保存其预期内容、位置和点赞到本地忽略文件；第二条命令只检查，不新增评论。

## 推荐提交内容

评审说明第一屏放在线地址、两个账号与密码、约一分钟演示视频、源码包入口。源码附 README、Git 提交历史和测试记录。视频应并排展示两个用户，优先展示实时协作，再展示情绪与整理。
