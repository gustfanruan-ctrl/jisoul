import json
import requests

# 读取 JSON
with open('D:/jisoul/jisoul_knowledge_optimized.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"上传 {len(data['cards'])} 张卡片...")

# 发送请求
response = requests.post(
    'http://localhost:8000/api/v1/knowledge/import',
    json={'items': data['cards']},
    timeout=300
)

print(f"状态码: {response.status_code}")
print(response.text)