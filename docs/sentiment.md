# 情绪模型与配置

配置完整时优先调用大模型 API；未配置、超时、限流或输出无效时回退本地模型。两种方式都不可用时保留评论并显示「待判断」，不会伪装成中性。

## 大模型 API

在 Railway 后端环境变量（或本地 `.env`，启动时加 `--env-file .env`）设置三项：

```dotenv
SENTIMENT_API_BASE_URL=https://your-provider.example/v1
SENTIMENT_API_MODEL=your-model-name
SENTIMENT_API_KEY=your-secret-key
```

服务使用 `{base_url}/chat/completions`，要求支持 JSON 对象输出。兼容该协议的提供商可使用相应地址和模型名；密钥仅在后端读取，不进入前端、Git 或评论数据。改变配置后重启服务。当前交付环境没有配置真实 API 密钥，因此默认实际运行本地模型；API 路径由模拟 HTTP 服务验证，没有产生付费模型调用。

只发送评论正文，不发送作者、头像、账号、点赞等信息。系统提示规定正向、负向、中性三类，并将评论作为数据传入；模型仍可能受复杂表达影响。接口超时为 6 秒，失败后 60 秒内跳过接口并使用本地推理，随后新请求可尝试恢复。

## 本地模型

采用 [lxyuan/distilbert-base-multilingual-cased-sentiments-student](https://huggingface.co/lxyuan/distilbert-base-multilingual-cased-sentiments-student)，是支持中文的多语言情绪分类模型，并非自行训练的词库。运行 [Xenova 的 ONNX 量化版本](https://huggingface.co/Xenova/distilbert-base-multilingual-cased-sentiments-student)，固定提交 `9d9ac661fd7b0b48535a1fc99b20ae6947629e65`。

模型文件 135,953,840 字节（约 136 MB），分词器约 2.9 MB。只需 CPU；ONNX Runtime 限制单线程、单个模型实例串行推理，避免并发推理放大内存。模型按需加载：API 正常时不加载本地权重。超过 512 token 的评论使用有重叠的多个分块推理后汇总，避免直接丢弃结尾。

本地首次运行执行：

```sh
python scripts/download_sentiment_model.py
```

下载固定版本并校验 SHA-256。Docker 构建时完成下载，运行时不依赖 Hugging Face 网络，也不执行远程模型代码。权重位于 `models/sentiment/`，不进入源码 Git；源码包包含下载脚本、固定版本、校验值及许可说明。模型采用 Apache-2.0，许可原文见 `model-license.txt`。

模型输出三类概率，最高分不足 0.55 时标记为待判断。这是保守的应用阈值，不代表概率经过校准或具备承诺的准确率；例如「最近公司跨部门沟通困难」在该小模型中判断不确定，当前应显示待判断。复杂转折、反讽和领域表达可能出错，要求更好的语义判断时应配置大模型 API。

## 资源实测与持久化

在本次 Windows 开发电脑，单独模型进程的物理内存约 281 MiB，模型加载约 0.33 秒；短评中位数 9.6 毫秒，512 token 中位数约 403 毫秒。这不是 Railway 的性能承诺，完整 Web 服务和连接池还需额外内存；Windows 提交内存高于常驻物理内存。建议为完整服务预留约 1 GB，免费额度和实际用量以托管平台为准。

分类结果、来源、置信度和模型配置签名与评论正文版本一起保存。只在发表/修改时计算；相同请求重试、移动、点赞、浏览均不重复调用接口。已有评论在模型配置改变后于启动时重新分类，保留正文、位置、时间和点赞；模型配置未改变时复用已保存结果。首次迁移耗时随评论数量和 API 延迟增加。

本次验收覆盖：API 优先、无配置使用本地、超时回退与恢复、异常结果待判断、真实量化模型、长文本分块、结果持久化，以及移动/点赞不重新分类。实际分类效果需在业务样本上评估，不将少数验收样例当作整体准确率。
