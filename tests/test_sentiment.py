import unittest

from backend.sentiment import classify


class SentimentTests(unittest.TestCase):
    def test_positive_negative_and_neutral(self):
        examples = {
            "感谢公司提供的培训，非常好用，提升了效率！": "positive",
            "这个系统很差，经常闪退，太浪费时间了。": "negative",
            "明天下午三点在二楼会议室开会。": "neutral",
            "这个工具不好用，也不稳定": "negative",
            "这个工具不是很好": "negative",
            "目前没有问题，使用很顺畅": "positive",
            "不是不满意，我很喜欢": "positive",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(classify(text), expected)


