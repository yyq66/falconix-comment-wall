# 实时评论墙

鹰眼智能 2027 校园招聘代码考核。基于随题 Figma 原型，采用 Vue 3 + TypeScript + FastAPI，实现多人共享便签墙。

不提供注册；底部工具为新增、鼠标选择、拖动；卡片内点赞。

## 开发启动

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另开一个终端：

```sh
cd frontend
npm ci
npm run dev
```

浏览器访问 http://127.0.0.1:5173 。生产构建后 FastAPI 直接提供前端，无需单独启动 Vite。

## 检查

```sh
python -m unittest discover -s tests -v
cd frontend
npm run build
```

分阶段提交及测试记录见 `docs/development.md`。
