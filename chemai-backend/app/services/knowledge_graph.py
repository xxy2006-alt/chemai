"""
化学知识图谱服务
基于PubChem开源数据 + 人教版教材知识点映射
支持: 知识点查询/题目关联/历年真题检索
"""
import json
import os
from typing import List, Dict, Optional
from app.core.config import settings

# Chroma向量数据库
import chromadb
from chromadb.config import Settings as ChromaSettings


class KnowledgeGraphService:
    """
    化学知识图谱服务
    MVP阶段: 50个高频考点
    v1.1阶段: 120个核心知识点
    v1.2阶段: 200个知识点完整覆盖
    """

    def __init__(self):
        self.chroma_client = None
        self.collection = None
        self.knowledge_points = {}  # 内存知识图谱
        self._init_knowledge_graph()

    def _init_knowledge_graph(self):
        """初始化知识图谱"""
        # 初始化Chroma
        try:
            # 确保数据目录存在
            os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
            # 使用 PersistentClient API，禁用 telemetry 避免 posthog 错误
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_DB_PATH,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="chemistry_knowledge",
                metadata={"description": "高中化学知识图谱"}
            )
        except Exception as e:
            print(f"Chroma初始化失败: {e}")
            self.chroma_client = None
            self.collection = None

        # 加载知识点
        self._load_knowledge_points()

    def _load_knowledge_points(self):
        """从文件加载知识点数据"""
        kp_file = os.path.join(settings.KNOWLEDGE_GRAPH_PATH, "knowledge_points.json")
        if os.path.exists(kp_file):
            with open(kp_file, "r", encoding="utf-8") as f:
                self.knowledge_points = json.load(f)
        else:
            # MVP初始50个高频考点
            self.knowledge_points = self._get_mvp_knowledge_points()
            self._save_knowledge_points()

    def _save_knowledge_points(self):
        """保存知识点数据"""
        os.makedirs(settings.KNOWLEDGE_GRAPH_PATH, exist_ok=True)
        kp_file = os.path.join(settings.KNOWLEDGE_GRAPH_PATH, "knowledge_points.json")
        with open(kp_file, "w", encoding="utf-8") as f:
            json.dump(self.knowledge_points, f, ensure_ascii=False, indent=2)

    def _get_mvp_knowledge_points(self) -> Dict:
        """
        MVP阶段50个高频考点
        基于PRD附录B
        """
        return {
            # 电解质溶液
            "电解质溶液": {
                "category": "电解质溶液",
                "description": "电解质在水溶液或熔融状态下的电离",
                "related_kps": ["电离", "离子反应", "盐类水解"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            "电离": {
                "category": "电解质溶液",
                "description": "电解质形成离子的过程",
                "related_kps": ["电解质溶液", "离子反应"],
                "pubchem_cid": None,
                "difficulty": "easy",
                "exam_frequency": "high"
            },
            "盐类水解": {
                "category": "电解质溶液",
                "description": "盐溶液呈现酸碱性的原因",
                "related_kps": ["电解质溶液", "水的离子积", "电离常数"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "very_high"
            },
            # 离子反应
            "离子反应": {
                "category": "离子反应",
                "description": "溶液中离子之间的反应",
                "related_kps": ["电离", "电解质溶液"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            # 氧化还原反应
            "氧化还原反应": {
                "category": "氧化还原反应",
                "description": "反应中电子的转移",
                "related_kps": ["电离", "原电池", "电解池"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "very_high"
            },
            # 原电池
            "原电池": {
                "category": "电化学",
                "description": "将化学能转化为电能的装置",
                "related_kps": ["氧化还原反应", "电解池", "金属腐蚀"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "very_high"
            },
            # 电解池
            "电解池": {
                "category": "电化学",
                "description": "将电能转化为化学能的装置",
                "related_kps": ["氧化还原反应", "原电池", "电离"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "very_high"
            },
            # 物质的量
            "物质的量": {
                "category": "化学计量",
                "description": "表示一定数目粒子集合体的物理量",
                "related_kps": ["阿伏伽德罗常数", "摩尔质量", "气体摩尔体积"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "very_high"
            },
            "阿伏伽德罗常数": {
                "category": "化学计量",
                "description": "1mol物质含有的粒子数",
                "related_kps": ["物质的量", "摩尔质量"],
                "pubchem_cid": None,
                "difficulty": "easy",
                "exam_frequency": "high"
            },
            "摩尔质量": {
                "category": "化学计量",
                "description": "单位物质的量的物质具有的质量",
                "related_kps": ["物质的量", "相对原子质量"],
                "pubchem_cid": None,
                "difficulty": "easy",
                "exam_frequency": "high"
            },
            # 元素周期律
            "元素周期律": {
                "category": "物质结构",
                "description": "元素性质随原子序数的周期性变化",
                "related_kps": ["原子结构", "离子半径", "电负性"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            "原子结构": {
                "category": "物质结构",
                "description": "原子的组成及结构",
                "related_kps": ["元素周期律", "核素", "电子排布"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            # 化学反应速率与平衡
            "化学反应速率": {
                "category": "化学反应速率与平衡",
                "description": "化学反应进行的快慢",
                "related_kps": ["勒夏特列原理", "化学平衡", "活化能"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "high"
            },
            "化学平衡": {
                "category": "化学反应速率与平衡",
                "description": "正逆反应速率相等时的状态",
                "related_kps": ["勒夏特列原理", "化学反应速率", "平衡常数"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "very_high"
            },
            "勒夏特列原理": {
                "category": "化学反应速率与平衡",
                "description": "平衡移动原理",
                "related_kps": ["化学平衡", "化学反应速率"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            # 有机化学基础
            "有机化合物": {
                "category": "有机化学",
                "description": "含碳的化合物",
                "related_kps": ["官能团", "同分异构体", "取代反应"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            "官能团": {
                "category": "有机化学",
                "description": "决定有机物性质的原子或原子团",
                "related_kps": ["有机化合物", "同分异构体"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "very_high"
            },
            "同分异构体": {
                "category": "有机化学",
                "description": "分子式相同但结构不同的化合物",
                "related_kps": ["官能团", "有机化合物"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "very_high"
            },
            "酯化反应": {
                "category": "有机化学",
                "description": "酸与醇生成酯和水的反应",
                "related_kps": ["官能团", "酯", "取代反应"],
                "pubchem_cid": None,
                "difficulty": "hard",
                "exam_frequency": "high"
            },
            # 物质结构
            "共价键": {
                "category": "物质结构",
                "description": "原子间通过共用电子形成的化学键",
                "related_kps": ["离子键", "分子间作用力", "氢键"],
                "pubchem_cid": None,
                "difficulty": "medium",
                "exam_frequency": "high"
            },
            "离子键": {
                "category": "物质结构",
                "description": "阴阳离子间的静电作用",
                "related_kps": ["共价键", "电子式"],
                "pubchem_cid": None,
                "difficulty": "easy",
                "exam_frequency": "high"
            },
            # (继续添加剩余30个...)
        }

    def get_knowledge_point(self, name: str) -> Optional[Dict]:
        """获取知识点详情"""
        return self.knowledge_points.get(name)

    def search_knowledge_points(self, keyword: str) -> List[Dict]:
        """搜索知识点"""
        results = []
        keyword_lower = keyword.lower()
        for name, kp in self.knowledge_points.items():
            if keyword_lower in name.lower() or keyword_lower in kp.get("description", "").lower():
                results.append({"name": name, **kp})
        return results

    def get_related_knowledge_points(self, name: str) -> List[str]:
        """获取相关知识点"""
        kp = self.get_knowledge_point(name)
        if kp:
            return kp.get("related_kps", [])
        return []

    def add_knowledge_point(self, name: str, data: Dict):
        """添加知识点"""
        self.knowledge_points[name] = data
        self._save_knowledge_points()

        # 添加到向量数据库
        if self.collection:
            self.collection.add(
                documents=[f"{name}: {data.get('description', '')}"],
                metadatas=[{"name": name, "category": data.get("category", "")}],
                ids=[name]
            )

    def query_similar_knowledge(self, text: str, limit: int = 5) -> List[Dict]:
        """查询相似知识点(使用向量数据库)"""
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[text],
                n_results=limit
            )
            return results
        except Exception as e:
            print(f"Chroma查询失败: {e}")
            return []


# 全局知识图谱服务实例
kg_service = KnowledgeGraphService()
