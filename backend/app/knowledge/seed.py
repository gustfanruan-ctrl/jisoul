# 文件路径：backend/app/knowledge/seed.py
# 用途：预置知识库种子数据，首次启动时自动灌入
# MVP 范围：10 条覆盖常见场景的示例数据，方便演示和测试

import time
import uuid
from loguru import logger
from app.knowledge.store import vector_store


SEED_DATA = [
    {
        "content": "FineBI 的自助分析支持业务人员零代码拖拽建模，不需要写 SQL，业务人员平均 2 天就能上手。相比 Power BI 需要学 DAX 公式，FineBI 的学习门槛低很多，特别适合业务部门自己做分析。",
        "category": "竞品应对",
        "industry": "通用",
    },
    {
        "content": "我们在制造业有超过 500 家客户，包括三一重工、美的、海尔等头部企业。制造业最常用的场景是生产看板、质量追溯、设备 OEE 分析。平均实施周期 2-3 个月可以跑通第一个场景。",
        "category": "行业案例",
        "industry": "制造",
    },
    {
        "content": "关于数据安全，我们支持行级列级权限控制，所有数据传输 HTTPS 加密，支持私有化部署，数据不出客户网络。已通过等保三级认证和 ISO 27001 认证。",
        "category": "安全合规",
        "industry": "通用",
    },
    {
        "content": "和 Tableau 相比，我们的核心差异是：1）中文场景优化更好，文档和服务全中文；2）价格约为 Tableau 的 1/3；3）支持私有化部署，Tableau Cloud 只能公有云；4）本地化服务团队响应更快。",
        "category": "竞品应对",
        "industry": "通用",
    },
    {
        "content": "报价策略：标准版按并发用户数计费，10 个并发起步，每增加 10 个并发阶梯递减。企业版按命名用户数计费，100 用户起步。建议客户先用标准版 POC，再根据实际用量选版本。",
        "category": "价格异议",
        "industry": "通用",
    },
    {
        "content": "零售行业客户最关注的三个场景：门店销售日报自动推送、会员复购分析、库存周转预警。我们有永辉超市、名创优品等标杆案例，门店数据分析从 T+3 降到 T+0。",
        "category": "行业案例",
        "industry": "零售",
    },
    {
        "content": "实施过程中最常见的问题是数据源对接。我们支持 50+ 种数据源直连，包括 MySQL、Oracle、SQL Server、ClickHouse、Hive 等主流数据库，以及用友、金蝶等 ERP 系统的 API 对接。",
        "category": "技术实施",
        "industry": "通用",
    },
    {
        "content": "金融行业客户最看重监管合规。我们已经为多家银行和证券公司提供了私有化部署方案，支持国密算法加密、审计日志全留痕、数据脱敏展示。参考客户：招商银行信用卡中心、华泰证券。",
        "category": "行业案例",
        "industry": "金融",
    },
    {
        "content": "如果客户说预算有限，可以建议分期实施方案：第一期只做核心报表和管理驾驶舱，3 个月上线，费用控制在 20 万以内；第二期再扩展自助分析和移动端，根据第一期效果申请追加预算。",
        "category": "价格异议",
        "industry": "通用",
    },
    {
        "content": "电商行业重点场景：实时 GMV 大屏、流量转化漏斗分析、活动效果复盘、商品动销分析。我们支持对接淘宝、京东、拼多多等平台 API，也支持自建站 MySQL 直连。某头部电商客户通过转化漏斗优化，将购买转化率提升了 15%。",
        "category": "行业案例",
        "industry": "电商",
    },
]


def seed_knowledge_base() -> int:
    """灌入种子数据（如果知识库为空）

    Returns:
        灌入的条数，0 表示已有数据不灌入
    """
    current_count = vector_store.count()
    if current_count > 0:
        logger.info(f"知识库已有 {current_count} 条数据，跳过种子灌入")
        return 0

    logger.info(f"知识库为空，开始灌入 {len(SEED_DATA)} 条种子数据...")

    ids = []
    documents = []
    metadatas = []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for i, item in enumerate(SEED_DATA):
        chunk_id = f"chunk_seed_{uuid.uuid4().hex[:8]}"
        ids.append(chunk_id)
        documents.append(item["content"])
        metadatas.append({
            "file_id": "seed",
            "file_name": "预置种子数据",
            "category": item["category"],
            "industry": item["industry"],
            "created_at": now,
            "chunk_index": i,
        })

    vector_store.add_chunks(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"种子数据灌入完成: {len(ids)} 条")
    return len(ids)