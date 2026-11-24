import re

# Original deterministic Chinese rules retained as the API fallback.
POSITIVE = {
    "非常好", "很好", "好用", "满意", "感谢", "赞", "开心", "幸福", "方便", "高效", "顺畅",
    "优秀", "清晰", "透明", "提升", "改善", "支持", "值得", "实用", "有用", "很棒", "不错",
    "喜欢", "认可", "推广", "坦诚", "有底气", "重视", "成功", "减少内耗", "减少无效内耗", "没有问题", "没问题",
}
NEGATIVE = {
    "不好用", "不满意", "不合理", "不稳定", "不方便", "不好", "差劲", "很差", "糟糕", "失望",
    "加班", "低效", "内耗", "过高", "太高", "太吵", "很慢", "压力", "问题", "难用", "闪退",
    "失败", "浪费", "反复", "倒挂", "留不住", "抱怨", "严重", "过时", "消耗", "降低", "犯困",
    "拖延", "无效", "模糊", "黑洞", "太多", "太长", "太慢", "讨厌", "崩溃", "错误", "不行",
}
TOKENS = re.compile("|".join(re.escape(w) for w in sorted(POSITIVE | NEGATIVE, key=len, reverse=True)))
NEGATION = re.compile(r"(?:不是|并不|没有|不|没|未)[太很够是]*$")


def classify(text: str):
    score = 0.0
    clauses = re.split(r"[。！？!?；;\n]|但是|不过|然而|但", text)
    for index, clause in enumerate(clauses):
        subtotal = 0
        for match in TOKENS.finditer(clause):
            token = match.group()
            value = 1 if token in POSITIVE else -1
            if NEGATION.search(clause[max(0, match.start()-5):match.start()]):
                value *= -1
            subtotal += value
        score += subtotal * (1.5 if index == len(clauses)-1 and len(clauses) > 1 else 1)
    return "positive" if score > .5 else "negative" if score < -.5 else "neutral"
